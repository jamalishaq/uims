from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User
from app.models.student import Student
from app.models.course import CourseSection, CourseEnrollment, EnrollmentStatus
from app.schemas.enrollment import EnrollRequest
from app.services.enrollment_service import (
    check_prerequisites,
    check_credit_load,
    check_duplicate_enrollment,
)

router = APIRouter()


@router.get("")
async def my_enrollments(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")

    result = await db.execute(
        select(CourseEnrollment)
        .where(
            CourseEnrollment.student_id == student.id,
            CourseEnrollment.status == EnrollmentStatus.REGISTERED,
        )
        .options(
            selectinload(CourseEnrollment.section).selectinload(CourseSection.course)
        )
    )
    enrollments = result.scalars().all()

    return [
        {
            "id": e.id,
            "section_id": e.section_id,
            "status": e.status,
            "course_code": e.section.course.code,
            "course_title": e.section.course.title,
            "credit_hours": e.section.course.credit_hours,
            "course_type": e.section.course.course_type,
            "schedule": e.section.schedule,
            "venue": e.section.venue,
            "ca_score": e.ca_score,
            "exam_score": e.exam_score,
            "total_score": e.total_score,
            "grade": e.grade,
            "passed": e.passed,
        }
        for e in enrollments
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def enroll(
    body: EnrollRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()

    section = await db.get(CourseSection, body.section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Course section not found")

    await check_duplicate_enrollment(student.id, body.section_id, db)
    await check_prerequisites(student.id, section.course_id, db)
    await check_credit_load(student.id, body.section_id, db)

    db.add(CourseEnrollment(student_id=student.id, section_id=body.section_id))
    await db.commit()
    return {"message": "Enrolled successfully"}


@router.delete("/{enrollment_id}")
async def drop_course(
    enrollment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()

    enrollment = await db.get(CourseEnrollment, enrollment_id)
    if not enrollment or enrollment.student_id != student.id:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    enrollment.status = EnrollmentStatus.DROPPED
    await db.commit()
    return {"message": "Course dropped"}
