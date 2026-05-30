from pydantic import BaseModel
from app.models.payment import FeeType, PaymentStatus


class FeeScheduleCreate(BaseModel):
    semester_id: int
    program_id: int | None = None
    fee_type: FeeType
    amount: float


class FeeScheduleOut(BaseModel):
    id: int
    semester_id: int
    program_id: int | None = None
    fee_type: FeeType
    amount: float
    model_config = {"from_attributes": True}


class PaymentOut(BaseModel):
    id: int
    student_id: int
    semester_id: int | None = None
    fee_type: FeeType
    amount_due: float
    amount_paid: float
    balance: float
    status: PaymentStatus
    paystack_reference: str | None = None
    model_config = {"from_attributes": True}
