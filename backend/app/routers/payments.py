from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
import uuid

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.models.student import Student
from app.models.payment import Payment, PaymentStatus, FeeSchedule, FeeType
from app.models.calendar import Semester
from app.schemas.payments import FeeScheduleCreate, FeeScheduleOut, PaymentOut
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


@router.get("/my", response_model=list[PaymentOut])
async def my_payments(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student record not found")
    result = await db.execute(select(Payment).where(Payment.student_id == student.id))
    return result.scalars().all()


@router.get("/schedule", response_model=list[FeeScheduleOut])
async def get_fee_schedule(
    semester_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if semester_id is None:
        sem_result = await db.execute(select(Semester).where(Semester.is_current == True))
        semester = sem_result.scalar_one_or_none()
        if not semester:
            return []
        semester_id = semester.id
    result = await db.execute(select(FeeSchedule).where(FeeSchedule.semester_id == semester_id))
    return result.scalars().all()


@router.post("/schedule", response_model=FeeScheduleOut, status_code=status.HTTP_201_CREATED)
async def create_fee_schedule(
    body: FeeScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("bursar", "super_admin")),
):
    obj = FeeSchedule(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.post("/generate", response_model=list[PaymentOut])
async def generate_payments(
    student_id: int = Query(...),
    semester_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("bursar", "registrar")),
):
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "Student not found")

    schedules_result = await db.execute(
        select(FeeSchedule).where(
            FeeSchedule.semester_id == semester_id,
            or_(FeeSchedule.program_id == student.program_id, FeeSchedule.program_id == None),
        )
    )
    schedules = schedules_result.scalars().all()

    created = []
    for fs in schedules:
        existing = await db.execute(
            select(Payment).where(
                Payment.student_id == student.id,
                Payment.semester_id == semester_id,
                Payment.fee_type == fs.fee_type,
            )
        )
        if existing.scalar_one_or_none():
            continue
        payment = Payment(
            student_id=student.id,
            semester_id=semester_id,
            fee_type=fs.fee_type,
            amount_due=fs.amount,
            amount_paid=0.0,
            balance=fs.amount,
        )
        db.add(payment)
        created.append(payment)

    await db.commit()
    for p in created:
        await db.refresh(p)
    return created
