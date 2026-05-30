from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role

router = APIRouter()


@router.post("/sections/{section_id}")
async def mark_attendance(section_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_role("lecturer"))):
    # TODO: accept list of {student_id, status} and create AttendanceRecord + entries
    pass


@router.get("/sections/{section_id}/summary")
async def attendance_summary(section_id: int, db: AsyncSession = Depends(get_db)):
    # TODO: per student: total lectures, attended, percentage — flag those below 75%
    pass
