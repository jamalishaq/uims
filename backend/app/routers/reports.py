from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.student import Student, StudentStatus
from app.models.course import CourseEnrollment, CourseSection
from app.models.payment import Payment, PaymentStatus
from app.models.academic import Program

router = APIRouter()


@router.get("/enrollment-stats")
async def enrollment_stats(
    semester_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("super_admin", "registrar", "hod", "dean")),
):
    stmt = (
        select(
            Student.program_id,
            Program.name.label("program_name"),
            Student.level,
            func.count(Student.id.distinct()).label("student_count"),
        )
        .join(Program, Student.program_id == Program.id)
        .join(CourseEnrollment, CourseEnrollment.student_id == Student.id)
        .join(CourseSection, CourseEnrollment.section_id == CourseSection.id)
        .group_by(Student.program_id, Program.name, Student.level)
    )
    if semester_id is not None:
        stmt = stmt.where(CourseSection.semester_id == semester_id)

    result = await db.execute(stmt)
    return [
        {"program_id": r.program_id, "program_name": r.program_name, "level": r.level, "student_count": r.student_count}
        for r in result.all()
    ]


@router.get("/pass-fail")
async def pass_fail_rates(
    semester_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("hod", "dean", "super_admin")),
):
    from app.models.course import Course
    stmt = (
        select(
            CourseSection.id.label("section_id"),
            Course.code.label("course_code"),
            Course.title.label("course_title"),
            CourseSection.semester_id,
            func.count(CourseEnrollment.id).label("total"),
            func.sum(case((CourseEnrollment.passed == True, 1), else_=0)).label("passed"),
            func.sum(case((CourseEnrollment.passed == False, 1), else_=0)).label("failed"),
        )
        .join(Course, CourseSection.course_id == Course.id)
        .join(CourseEnrollment, CourseEnrollment.section_id == CourseSection.id)
        .where(CourseEnrollment.grade != None)
        .group_by(CourseSection.id, Course.code, Course.title, CourseSection.semester_id)
    )
    if semester_id is not None:
        stmt = stmt.where(CourseSection.semester_id == semester_id)

    result = await db.execute(stmt)
    return [
        {
            "section_id": r.section_id,
            "course_code": r.course_code,
            "course_title": r.course_title,
            "semester_id": r.semester_id,
            "total": r.total,
            "passed": r.passed or 0,
            "failed": r.failed or 0,
            "pass_rate": round((r.passed or 0) / r.total * 100, 1) if r.total else 0.0,
        }
        for r in result.all()
    ]


@router.get("/fee-collection")
async def fee_collection(
    semester_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("bursar", "super_admin")),
):
    stmt = (
        select(
            Payment.fee_type,
            func.sum(Payment.amount_due).label("total_due"),
            func.sum(Payment.amount_paid).label("total_collected"),
            func.sum(Payment.balance).label("total_outstanding"),
            func.count(Payment.id).label("student_count"),
        )
        .group_by(Payment.fee_type)
    )
    if semester_id is not None:
        stmt = stmt.where(Payment.semester_id == semester_id)

    result = await db.execute(stmt)
    return [
        {
            "fee_type": r.fee_type,
            "total_due": round(r.total_due or 0, 2),
            "total_collected": round(r.total_collected or 0, 2),
            "total_outstanding": round(r.total_outstanding or 0, 2),
            "student_count": r.student_count,
        }
        for r in result.all()
    ]


@router.get("/cgpa-distribution")
async def cgpa_distribution(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("dean", "hod", "super_admin")),
):
    result = await db.execute(
        select(Student.cgpa).where(Student.status == StudentStatus.ACTIVE)
    )
    cgpas = [row[0] for row in result.all()]

    buckets = {"0.0–1.0": 0, "1.0–2.0": 0, "2.0–3.0": 0, "3.0–4.0": 0, "4.0–5.0": 0}
    for cgpa in cgpas:
        if cgpa < 1.0:
            buckets["0.0–1.0"] += 1
        elif cgpa < 2.0:
            buckets["1.0–2.0"] += 1
        elif cgpa < 3.0:
            buckets["2.0–3.0"] += 1
        elif cgpa < 4.0:
            buckets["3.0–4.0"] += 1
        else:
            buckets["4.0–5.0"] += 1

    return [{"range": k, "count": v} for k, v in buckets.items()]
