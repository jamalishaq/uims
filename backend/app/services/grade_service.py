from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.course import CourseEnrollment, CourseSection
from app.models.grade import GradeScale
from app.models.student import Student


async def compute_grade(score: float, db: AsyncSession, faculty_id: int | None = None) -> tuple[str, float, bool]:
    """
    Returns (grade_letter, grade_points, passed).
    Faculty-specific scale takes precedence over university-wide (faculty_id=None).
    """
    result = await db.execute(
        select(GradeScale)
        .where(
            GradeScale.min_score <= score,
            GradeScale.max_score >= score,
        )
        .order_by(GradeScale.faculty_id.desc().nulls_last())
        .limit(1)
    )
    scale = result.scalar_one_or_none()
    if not scale:
        raise ValueError(f"No grade scale configured for score {score}")
    return scale.grade, scale.grade_points, scale.passed


async def recalculate_cgpa(student_id: int, db: AsyncSession) -> float:
    """Recomputes and persists CGPA and total_credits_passed for a student."""
    result = await db.execute(
        select(CourseEnrollment)
        .where(
            CourseEnrollment.student_id == student_id,
            CourseEnrollment.grade_points.is_not(None),
        )
        .options(selectinload(CourseEnrollment.section).selectinload(CourseSection.course))
    )
    enrollments = result.scalars().all()

    total_weighted = sum(e.grade_points * e.section.course.credit_hours for e in enrollments)
    total_credits = sum(e.section.course.credit_hours for e in enrollments)

    cgpa = round(total_weighted / total_credits, 2) if total_credits > 0 else 0.0
    credits_passed = sum(e.section.course.credit_hours for e in enrollments if e.passed)

    student = await db.get(Student, student_id)
    student.cgpa = cgpa
    student.total_credits_passed = credits_passed
    await db.commit()
    return cgpa
