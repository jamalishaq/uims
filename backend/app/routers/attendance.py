from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
from datetime import date as date_type

from app.core.database import get_db
from app.core.dependencies import require_role, get_current_user
from app.models.attendance import AttendanceRecord, AttendanceEntry, AttendanceStatus
from app.models.course import CourseSection, CourseEnrollment, EnrollmentStatus
from app.models.student import Student
from app.models.user import User
from app.schemas.attendance import MarkAttendanceRequest, AttendanceSummaryItem
from app.schemas.common import MessageResponse

router = APIRouter()


@router.get("/my", response_model=list[dict])
async def my_attendance(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    student_result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(404, "Student record not found")

    # Get all active enrollments
    enrollments_result = await db.execute(
        select(CourseEnrollment)
        .where(
            CourseEnrollment.student_id == student.id,
            CourseEnrollment.status == EnrollmentStatus.REGISTERED,
        )
        .options(selectinload(CourseEnrollment.section).selectinload(CourseSection.course))
    )
    enrollments = enrollments_result.scalars().all()

    result = []
    for enrollment in enrollments:
        section = enrollment.section
        total_result = await db.execute(
            select(func.count()).where(AttendanceRecord.section_id == section.id)
        )
        total_classes = total_result.scalar() or 0

        attended_result = await db.execute(
            select(func.count())
            .select_from(AttendanceEntry)
            .join(AttendanceRecord, AttendanceEntry.record_id == AttendanceRecord.id)
            .where(
                AttendanceRecord.section_id == section.id,
                AttendanceEntry.student_id == student.id,
                AttendanceEntry.status == AttendanceStatus.PRESENT,
            )
        )
        attended = attended_result.scalar() or 0
        percentage = (attended / total_classes * 100) if total_classes > 0 else 0.0

        result.append({
            "section_id": section.id,
            "course_code": section.course.code,
            "course_title": section.course.title,
            "total_classes": total_classes,
            "attended": attended,
            "percentage": round(percentage, 1),
            "below_threshold": percentage < 75,
        })

    return result


@router.get("/{section_id}/summary", response_model=list[AttendanceSummaryItem])
async def attendance_summary(
    section_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("lecturer", "hod", "dean")),
):
    # Total classes held for this section
    total_result = await db.execute(
        select(func.count()).where(AttendanceRecord.section_id == section_id)
    )
    total_classes = total_result.scalar() or 0

    # Get all students enrolled in this section
    enrollments_result = await db.execute(
        select(CourseEnrollment)
        .where(
            CourseEnrollment.section_id == section_id,
            CourseEnrollment.status == EnrollmentStatus.REGISTERED,
        )
        .options(selectinload(CourseEnrollment.student))
    )
    enrollments = enrollments_result.scalars().all()

    summary = []
    for enrollment in enrollments:
        student = enrollment.student
        # Count how many times this student was PRESENT
        attended_result = await db.execute(
            select(func.count())
            .select_from(AttendanceEntry)
            .join(AttendanceRecord, AttendanceEntry.record_id == AttendanceRecord.id)
            .where(
                AttendanceRecord.section_id == section_id,
                AttendanceEntry.student_id == student.id,
                AttendanceEntry.status == AttendanceStatus.PRESENT,
            )
        )
        attended = attended_result.scalar() or 0
        percentage = (attended / total_classes * 100) if total_classes > 0 else 0.0

        summary.append(AttendanceSummaryItem(
            student_id=student.id,
            matric_number=student.matric_number,
            total_classes=total_classes,
            attended=attended,
            percentage=round(percentage, 1),
            below_threshold=percentage < 75,
        ))

    return summary


@router.post("/{section_id}", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def mark_attendance(
    section_id: int,
    body: MarkAttendanceRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("lecturer")),
):
    section = await db.get(CourseSection, section_id)
    if not section:
        raise HTTPException(404, "Course section not found")
    if section.lecturer_id != user.id:
        raise HTTPException(403, "Not your course section")

    # Check if record already exists for this date
    existing = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.section_id == section_id,
            AttendanceRecord.date == body.date,
        )
    )
    record = existing.scalar_one_or_none()
    if record:
        # Delete existing entries and replace
        await db.execute(
            delete(AttendanceEntry).where(AttendanceEntry.record_id == record.id)
        )
    else:
        record = AttendanceRecord(section_id=section_id, date=body.date)
        db.add(record)
        await db.flush()  # get record.id

    for entry_data in body.entries:
        db.add(AttendanceEntry(
            record_id=record.id,
            student_id=entry_data.student_id,
            status=entry_data.status,
        ))

    await db.commit()
    return MessageResponse(message=f"Attendance marked for {len(body.entries)} students")
