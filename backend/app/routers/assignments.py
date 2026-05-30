from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.assignment import Assignment, Submission
from app.models.course import CourseEnrollment, CourseSection, EnrollmentStatus
from app.models.student import Student
from app.models.user import User
from app.schemas.assignments import (
    AssignmentCreate,
    AssignmentOut,
    GradeSubmissionRequest,
    SubmissionOut,
    SubmitAssignmentRequest,
)
from app.schemas.common import MessageResponse

router = APIRouter()


@router.get("", response_model=list[AssignmentOut])
async def list_assignments(
    section_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    section = await db.get(CourseSection, section_id)
    if not section:
        raise HTTPException(404, "Section not found")

    if user.role == "lecturer":
        if section.lecturer_id != user.id:
            raise HTTPException(403, "Not your section")
    elif user.role == "student":
        student_result = await db.execute(select(Student).where(Student.user_id == user.id))
        student = student_result.scalar_one_or_none()
        if not student:
            raise HTTPException(404, "Student record not found")
        enrollment = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.student_id == student.id,
                CourseEnrollment.section_id == section_id,
                CourseEnrollment.status == EnrollmentStatus.REGISTERED,
            )
        )
        if not enrollment.scalar_one_or_none():
            raise HTTPException(403, "Not enrolled in this section")
    else:
        raise HTTPException(403, "Access denied")

    result = await db.execute(select(Assignment).where(Assignment.section_id == section_id))
    return result.scalars().all()


@router.post("", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    body: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("lecturer")),
):
    section = await db.get(CourseSection, body.section_id)
    if not section:
        raise HTTPException(404, "Section not found")
    if section.lecturer_id != user.id:
        raise HTTPException(403, "Not your section")

    obj = Assignment(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@router.post("/{assignment_id}/submit", response_model=SubmissionOut)
async def submit_assignment(
    assignment_id: int,
    body: SubmitAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    assignment = await db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(404, "Assignment not found")

    student_result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student record not found")

    enrollment_result = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.student_id == student.id,
            CourseEnrollment.section_id == assignment.section_id,
            CourseEnrollment.status == EnrollmentStatus.REGISTERED,
        )
    )
    if not enrollment_result.scalar_one_or_none():
        raise HTTPException(403, "Not enrolled in this course")

    is_late = datetime.now(timezone.utc) > assignment.due_date.replace(tzinfo=timezone.utc)

    existing_result = await db.execute(
        select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.student_id == student.id,
        )
    )
    submission = existing_result.scalar_one_or_none()
    if submission:
        submission.file_url = body.file_url
        submission.is_late = is_late
    else:
        submission = Submission(
            assignment_id=assignment_id,
            student_id=student.id,
            file_url=body.file_url,
            is_late=is_late,
        )
        db.add(submission)

    await db.commit()
    await db.refresh(submission)
    return submission


@router.get("/{assignment_id}/submissions", response_model=list[SubmissionOut])
async def list_submissions(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("lecturer")),
):
    assignment = await db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    section = await db.get(CourseSection, assignment.section_id)
    if section.lecturer_id != user.id:
        raise HTTPException(403, "Not your assignment")

    result = await db.execute(
        select(Submission).where(Submission.assignment_id == assignment_id)
    )
    return result.scalars().all()


@router.post("/{assignment_id}/submissions/{submission_id}/grade", response_model=SubmissionOut)
async def grade_submission(
    assignment_id: int,
    submission_id: int,
    body: GradeSubmissionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("lecturer")),
):
    submission = await db.get(Submission, submission_id)
    if not submission or submission.assignment_id != assignment_id:
        raise HTTPException(404, "Submission not found")

    assignment = await db.get(Assignment, assignment_id)
    section = await db.get(CourseSection, assignment.section_id)
    if section.lecturer_id != user.id:
        raise HTTPException(403, "Not your assignment")

    if body.score > assignment.max_score:
        raise HTTPException(400, f"Score cannot exceed max score of {assignment.max_score}")

    submission.score = body.score
    submission.feedback = body.feedback
    await db.commit()
    await db.refresh(submission)
    return submission
