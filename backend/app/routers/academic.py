from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.academic import Faculty, Department, Program
from app.models.calendar import AcademicSession, Semester
from app.schemas.academic import (
    FacultyCreate, FacultyOut,
    DepartmentCreate, DepartmentOut,
    ProgramCreate, ProgramOut,
    SessionCreate, SessionOut,
    SemesterCreate, SemesterOut,
)

router = APIRouter()


@router.get("/faculties", response_model=list[FacultyOut])
async def list_faculties(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Faculty))
    return result.scalars().all()


@router.post("/faculties", response_model=FacultyOut, status_code=status.HTTP_201_CREATED)
async def create_faculty(body: FacultyCreate, db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin"))):
    obj = Faculty(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(faculty_id: int | None = Query(None), db: AsyncSession = Depends(get_db)):
    stmt = select(Department)
    if faculty_id is not None:
        stmt = stmt.where(Department.faculty_id == faculty_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(body: DepartmentCreate, db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin"))):
    obj = Department(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.get("/programs", response_model=list[ProgramOut])
async def list_programs(department_id: int | None = Query(None), db: AsyncSession = Depends(get_db)):
    stmt = select(Program)
    if department_id is not None:
        stmt = stmt.where(Program.department_id == department_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/programs", response_model=ProgramOut, status_code=status.HTTP_201_CREATED)
async def create_program(body: ProgramCreate, db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar"))):
    obj = Program(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AcademicSession))
    return result.scalars().all()


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar"))):
    if body.is_current:
        await db.execute(update(AcademicSession).values(is_current=False))
    obj = AcademicSession(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.post("/sessions/{session_id}/semesters", response_model=SemesterOut, status_code=status.HTTP_201_CREATED)
async def create_semester(session_id: int, body: SemesterCreate, db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar"))):
    session = await db.get(AcademicSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Academic session not found")
    if body.is_current:
        await db.execute(update(Semester).where(Semester.session_id == session_id).values(is_current=False))
    obj = Semester(session_id=session_id, **body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj
