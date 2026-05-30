from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.course import Course, CoursePrerequisite, CourseSection, CourseEnrollment, EnrollmentStatus

MAX_CREDIT_LOAD = 21


async def check_prerequisites(student_id: int, course_id: int, db: AsyncSession):
    result = await db.execute(
        select(CoursePrerequisite).where(CoursePrerequisite.course_id == course_id)
    )
    prereqs = result.scalars().all()

    for prereq in prereqs:
        passed = await db.execute(
            select(CourseEnrollment)
            .join(CourseEnrollment.section)
            .where(
                CourseEnrollment.student_id == student_id,
                CourseSection.course_id == prereq.prerequisite_id,
                CourseEnrollment.passed == True,
            )
        )
        if not passed.scalar_one_or_none():
            course = await db.get(Course, prereq.prerequisite_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prerequisite not met: {course.code} — {course.title}",
            )


async def check_credit_load(student_id: int, section_id: int, db: AsyncSession):
    section = await db.get(CourseSection, section_id)
    new_course = await db.get(Course, section.course_id)

    current_result = await db.execute(
        select(func.sum(Course.credit_hours))
        .join(CourseSection, CourseSection.course_id == Course.id)
        .join(CourseEnrollment, CourseEnrollment.section_id == CourseSection.id)
        .where(
            CourseEnrollment.student_id == student_id,
            CourseSection.semester_id == section.semester_id,
            CourseEnrollment.status == EnrollmentStatus.REGISTERED,
        )
    )
    current_credits = current_result.scalar() or 0

    if current_credits + new_course.credit_hours > MAX_CREDIT_LOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Adding {new_course.credit_hours} credits would exceed the {MAX_CREDIT_LOAD}-credit limit (currently at {current_credits})",
        )


async def check_duplicate_enrollment(student_id: int, section_id: int, db: AsyncSession):
    result = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.student_id == student_id,
            CourseEnrollment.section_id == section_id,
            CourseEnrollment.status == EnrollmentStatus.REGISTERED,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already enrolled in this section")
