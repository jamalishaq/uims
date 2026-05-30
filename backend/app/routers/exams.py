from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role

router = APIRouter()


@router.get("/timetable")
async def exam_timetable(db: AsyncSession = Depends(get_db)):
    # TODO: return exam schedule for current semester
    pass


@router.post("/timetable")
async def create_exam_slot(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar"))):
    pass
