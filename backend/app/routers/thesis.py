from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.student import Student
from app.models.thesis import Thesis, ThesisStatus
from app.schemas.thesis import (
    ThesisRegisterRequest,
    ThesisSubmitRequest,
    ThesisReviewRequest,
    ThesisResponse,
)

router = APIRouter()


@router.post("", response_model=ThesisResponse, status_code=status.HTTP_201_CREATED)
async def register_thesis(
    body: ThesisRegisterRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("student")),
):
    # Resolve the Student record for this user
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student record not found")

    # Ensure the student doesn't already have a thesis
    existing = await db.execute(select(Thesis).where(Thesis.student_id == student.id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thesis already registered")

    thesis = Thesis(
        student_id=student.id,
        supervisor_id=body.supervisor_id,
        title=body.title,
        abstract=body.abstract,
        status=ThesisStatus.TOPIC_SUBMITTED,
    )
    db.add(thesis)
    await db.commit()
    await db.refresh(thesis)
    return thesis


@router.get("/my", response_model=ThesisResponse)
async def get_my_thesis(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("student")),
):
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student record not found")

    result = await db.execute(select(Thesis).where(Thesis.student_id == student.id))
    thesis = result.scalar_one_or_none()
    if not thesis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No thesis found")
    return thesis


@router.post("/{thesis_id}/submit", response_model=ThesisResponse)
async def submit_thesis(
    thesis_id: int,
    body: ThesisSubmitRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("student")),
):
    # Resolve the Student record for this user
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student record not found")

    result = await db.execute(select(Thesis).where(Thesis.id == thesis_id))
    thesis = result.scalar_one_or_none()
    if not thesis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")

    if thesis.student_id != student.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your thesis")

    thesis.file_url = body.file_url
    thesis.status = ThesisStatus.SUBMITTED
    await db.commit()
    await db.refresh(thesis)
    return thesis


@router.post("/{thesis_id}/review", response_model=ThesisResponse)
async def review_thesis(
    thesis_id: int,
    body: ThesisReviewRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("lecturer", "dean")),
):
    result = await db.execute(select(Thesis).where(Thesis.id == thesis_id))
    thesis = result.scalar_one_or_none()
    if not thesis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")

    if body.action == "approve":
        thesis.status = ThesisStatus.APPROVED
    else:
        thesis.status = ThesisStatus.REJECTED

    if body.feedback is not None:
        thesis.supervisor_feedback = body.feedback

    await db.commit()
    await db.refresh(thesis)
    return thesis
