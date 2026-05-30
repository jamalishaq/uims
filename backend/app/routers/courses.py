from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role

router = APIRouter()


@router.get("")
async def list_courses(db: AsyncSession = Depends(get_db)):
    # TODO: filter by department, course_type, semester
    pass


@router.post("")
async def create_course(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "hod"))):
    pass


@router.post("/{course_id}/prerequisites")
async def add_prerequisite(course_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "hod"))):
    pass


@router.get("/sections")
async def list_sections(db: AsyncSession = Depends(get_db)):
    # TODO: filter by semester_id, course_id, lecturer_id
    pass


@router.post("/sections")
async def create_section(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "hod", "registrar"))):
    pass
