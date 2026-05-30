from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role

router = APIRouter()

# --- Faculties ---
@router.get("/faculties")
async def list_faculties(db: AsyncSession = Depends(get_db)):
    pass

@router.post("/faculties")
async def create_faculty(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin"))):
    pass

# --- Departments ---
@router.get("/departments")
async def list_departments(db: AsyncSession = Depends(get_db)):
    pass

@router.post("/departments")
async def create_department(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin"))):
    pass

# --- Programs ---
@router.get("/programs")
async def list_programs(db: AsyncSession = Depends(get_db)):
    pass

@router.post("/programs")
async def create_program(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar"))):
    pass

# --- Academic Sessions & Semesters ---
@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    pass

@router.post("/sessions")
async def create_session(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar"))):
    pass

@router.post("/sessions/{session_id}/semesters")
async def create_semester(session_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar"))):
    pass
