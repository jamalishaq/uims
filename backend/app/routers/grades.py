from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.models.student import Student
from app.models.course import CourseEnrollment, CourseSection
from app.schemas.grades import SubmitGradeRequest
from app.services.grade_service import compute_grade, recalculate_cgpa

router = APIRouter()


@router.post("/{enrollment_id}")
async def submit_grade(
    enrollment_id: int,
    body: SubmitGradeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("lecturer")),
):
    enrollment = await db.get(
        CourseEnrollment, enrollment_id,
        options=[selectinload(CourseEnrollment.section)]
    )
    if not enrollment:
        raise HTTPException(404, "Enrollment not found")
    if enrollment.section.lecturer_id != user.id:
        raise HTTPException(403, "Not your course section")

    total = body.ca_score + body.exam_score
    grade, grade_points, passed = await compute_grade(total, db)

    enrollment.ca_score = body.ca_score
    enrollment.exam_score = body.exam_score
    enrollment.total_score = total
    enrollment.grade = grade
    enrollment.grade_points = grade_points
    enrollment.passed = passed

    await db.commit()
    await recalculate_cgpa(enrollment.student_id, db)
    return {"grade": grade, "grade_points": grade_points, "passed": passed}


@router.get("/transcript/{student_id}")
async def get_transcript(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "student":
        result = await db.execute(select(Student).where(Student.user_id == user.id))
        student = result.scalar_one_or_none()
        if not student or student.id != student_id:
            raise HTTPException(403, "Access denied")

    result = await db.execute(
        select(CourseEnrollment)
        .where(CourseEnrollment.student_id == student_id, CourseEnrollment.grade != None)
        .options(selectinload(CourseEnrollment.section).selectinload(CourseSection.course))
        .order_by(CourseEnrollment.created_at)
    )
    enrollments = result.scalars().all()
    student = await db.get(Student, student_id)

    return {
        "student_id": student_id,
        "cgpa": student.cgpa,
        "total_credits_passed": student.total_credits_passed,
        "courses": [
            {
                "code": e.section.course.code,
                "title": e.section.course.title,
                "credit_hours": e.section.course.credit_hours,
                "ca": e.ca_score,
                "exam": e.exam_score,
                "total": e.total_score,
                "grade": e.grade,
                "grade_points": e.grade_points,
                "passed": e.passed,
            }
            for e in enrollments
        ],
    }
