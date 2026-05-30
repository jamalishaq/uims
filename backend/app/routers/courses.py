from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_role, get_current_user
from app.models.course import Course, CoursePrerequisite, CourseSection, CourseType
from app.schemas.courses import (
    CourseCreate, CourseOut,
    PrerequisiteCreate, PrerequisiteOut,
    SectionCreate, SectionOut,
)
from app.schemas.common import MessageResponse

router = APIRouter()


@router.get("", response_model=list[CourseOut])
async def list_courses(
    department_id: int | None = Query(None),
    course_type: CourseType | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Course).options(selectinload(Course.prerequisites))
    if department_id is not None:
        stmt = stmt.where(Course.department_id == department_id)
    if course_type is not None:
        stmt = stmt.where(Course.course_type == course_type)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    body: CourseCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("super_admin", "hod")),
):
    obj = Course(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    # Reload with prerequisites
    result = await db.execute(
        select(Course).where(Course.id == obj.id).options(selectinload(Course.prerequisites))
    )
    return result.scalar_one()


@router.get("/sections", response_model=list[SectionOut])
async def list_sections(
    semester_id: int | None = Query(None),
    course_id: int | None = Query(None),
    lecturer_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CourseSection)
    if semester_id is not None:
        stmt = stmt.where(CourseSection.semester_id == semester_id)
    if course_id is not None:
        stmt = stmt.where(CourseSection.course_id == course_id)
    if lecturer_id is not None:
        stmt = stmt.where(CourseSection.lecturer_id == lecturer_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/sections", response_model=SectionOut, status_code=status.HTTP_201_CREATED)
async def create_section(
    body: SectionCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("super_admin", "hod", "registrar")),
):
    obj = CourseSection(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.get("/{course_id}", response_model=CourseOut)
async def get_course(course_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Course).where(Course.id == course_id).options(selectinload(Course.prerequisites))
    )
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.post("/{course_id}/prerequisites", response_model=PrerequisiteOut, status_code=status.HTTP_201_CREATED)
async def add_prerequisite(
    course_id: int,
    body: PrerequisiteCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("super_admin", "hod")),
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    prereq_course = await db.get(Course, body.prerequisite_id)
    if not prereq_course:
        raise HTTPException(status_code=404, detail="Prerequisite course not found")
    if body.prerequisite_id == course_id:
        raise HTTPException(status_code=400, detail="A course cannot be its own prerequisite")
    obj = CoursePrerequisite(course_id=course_id, prerequisite_id=body.prerequisite_id)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj
