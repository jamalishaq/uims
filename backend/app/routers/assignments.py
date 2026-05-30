from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role

router = APIRouter()


@router.post("")
async def create_assignment(db: AsyncSession = Depends(get_db), user=Depends(require_role("lecturer"))):
    pass


@router.get("/sections/{section_id}")
async def list_assignments(section_id: int, db: AsyncSession = Depends(get_db)):
    pass


@router.post("/{assignment_id}/submit")
async def submit_assignment(assignment_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_role("student"))):
    # TODO: file upload to S3, create Submission record
    pass


@router.post("/submissions/{submission_id}/grade")
async def grade_submission(submission_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_role("lecturer"))):
    pass
