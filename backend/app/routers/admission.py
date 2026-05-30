from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role

router = APIRouter()


@router.post("/apply")
async def submit_application(db: AsyncSession = Depends(get_db), user=Depends(require_role("applicant"))):
    pass


@router.get("/applications")
async def list_applications(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar"))):
    # TODO: filter by status, program, session
    pass


@router.post("/applications/{application_id}/decision")
async def make_decision(application_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar"))):
    # TODO: accept / reject + send email via Celery
    pass


@router.post("/applications/{application_id}/enroll")
async def enroll_accepted_applicant(application_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar"))):
    # TODO: create Student record, generate matric number, set role to student
    pass
