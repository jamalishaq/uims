from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role

router = APIRouter()


@router.get("")
async def list_students(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("super_admin", "registrar", "hod", "dean")),
):
    # TODO: paginated list with filters (program, level, status)
    pass


@router.get("/{student_id}")
async def get_student(student_id: int, db: AsyncSession = Depends(get_db)):
    # TODO: student detail + current semester enrollment
    pass


@router.patch("/{student_id}/status")
async def update_student_status(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("super_admin", "registrar")),
):
    # TODO: activate / suspend / withdraw / graduate
    pass
