from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_role, get_current_user
from app.models.exam import ExamSlot
from app.models.course import CourseSection, CourseEnrollment, EnrollmentStatus
from app.models.user import User
from app.schemas.exams import ExamSlotCreate, ExamSlotOut

router = APIRouter()


@router.post("", response_model=ExamSlotOut, status_code=status.HTTP_201_CREATED)
async def create_exam_slot(
    body: ExamSlotCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("registrar", "super_admin")),
):
    section = await db.get(CourseSection, body.section_id)
    if not section:
        raise HTTPException(404, "Course section not found")
    obj = ExamSlot(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.get("", response_model=list[ExamSlotOut])
async def list_exam_slots(
    semester_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(ExamSlot).options(selectinload(ExamSlot.section))

    if semester_id is not None:
        stmt = stmt.join(CourseSection, ExamSlot.section_id == CourseSection.id).where(
            CourseSection.semester_id == semester_id
        )

    # Students only see exam slots for their enrolled sections
    if user.role == "student":
        from app.models.student import Student
        from sqlalchemy import select as sa_select
        student_result = await db.execute(
            sa_select(Student).where(Student.user_id == user.id)
        )
        student = student_result.scalar_one_or_none()
        if student:
            enrolled = await db.execute(
                sa_select(CourseEnrollment.section_id).where(
                    CourseEnrollment.student_id == student.id,
                    CourseEnrollment.status == EnrollmentStatus.REGISTERED,
                )
            )
            section_ids = [r[0] for r in enrolled.all()]
            stmt = stmt.where(ExamSlot.section_id.in_(section_ids))

    result = await db.execute(stmt.order_by(ExamSlot.date, ExamSlot.start_time))
    return result.scalars().all()
