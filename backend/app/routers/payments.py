from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.models.student import Student
from app.models.payment import Payment, PaymentStatus
from app.services.payment_service import initialize_transaction, verify_transaction

router = APIRouter()


@router.post("/initialize")
async def initiate_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()

    payment = await db.get(Payment, payment_id)
    if not payment or payment.student_id != student.id:
        raise HTTPException(404, "Payment record not found")
    if payment.status == PaymentStatus.PAID:
        raise HTTPException(400, "Already paid")

    reference = str(uuid.uuid4())
    data = await initialize_transaction(
        email=user.email,
        amount_naira=payment.balance,
        reference=reference,
        metadata={"payment_id": payment.id, "fee_type": payment.fee_type},
    )
    payment.paystack_reference = reference
    await db.commit()
    return {"authorization_url": data["authorization_url"], "reference": reference}


@router.post("/verify/{reference}")
async def verify_payment(
    reference: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = await verify_transaction(reference)
    if data["status"] != "success":
        raise HTTPException(400, "Payment not successful")

    result = await db.execute(select(Payment).where(Payment.paystack_reference == reference))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment record not found")

    amount_paid = data["amount"] / 100  # convert kobo to naira
    payment.amount_paid += amount_paid
    payment.balance = max(0, payment.amount_due - payment.amount_paid)
    payment.status = PaymentStatus.PAID if payment.balance == 0 else PaymentStatus.PARTIAL

    await db.commit()
    return {"status": payment.status, "balance": payment.balance}
