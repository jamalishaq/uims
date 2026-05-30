from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_role, get_current_user
from app.models.student import Student, StudentStatus
from app.models.user import User
from app.schemas.students import StudentListItem, StudentOut, StatusUpdateRequest
from app.schemas.common import PaginatedResponse, MessageResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[StudentListItem])
async def list_students(
    program_id: int | None = Query(None),
    level: int | None = Query(None),
    status: StudentStatus | None = Query(None),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("super_admin", "registrar", "hod", "dean")),
):
    stmt = select(Student).join(User, Student.user_id == User.id)
    if program_id is not None:
        stmt = stmt.where(Student.program_id == program_id)
    if level is not None:
        stmt = stmt.where(Student.level == level)
    if status is not None:
        stmt = stmt.where(Student.status == status)
    if q:
        stmt = stmt.where(
            or_(Student.matric_number.ilike(f"%{q}%"), User.username.ilike(f"%{q}%"))
        )

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar()

    result = await db.execute(stmt.offset((page - 1) * per_page).limit(per_page))
    students = result.scalars().all()
    pages = (total + per_page - 1) // per_page if per_page else 1

    return PaginatedResponse(items=students, total=total, page=page, per_page=per_page, pages=pages)


@router.get("/{student_id}")
async def get_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(Student)
        .where(Student.id == student_id)
        .options(selectinload(Student.user))
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return {
        "id": student.id,
        "user_id": student.user_id,
        "matric_number": student.matric_number,
        "program_id": student.program_id,
        "level": student.level,
        "status": student.status,
        "cgpa": student.cgpa,
        "total_credits_passed": student.total_credits_passed,
        "username": student.user.username,
        "email": student.user.email,
    }


@router.patch("/{student_id}/status", response_model=MessageResponse)
async def update_student_status(
    student_id: int,
    body: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("super_admin", "registrar")),
):
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    student.status = body.status
    await db.commit()
    return MessageResponse(message=f"Student status updated to {body.status}")
