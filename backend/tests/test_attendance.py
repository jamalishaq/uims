"""
Tests for /api/v1/attendance endpoints.
"""
import pytest
from datetime import date
from tests.conftest import auth, make_user
from app.models.user import UserRole
from app.models.course import CourseEnrollment, CourseSection
from app.models.attendance import AttendanceRecord, AttendanceEntry, AttendanceStatus


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def create_enrollment(db, student_id, section_id):
    e = CourseEnrollment(student_id=student_id, section_id=section_id)
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return e


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_attendance_success(client, db, lecturer, student, section):
    await create_enrollment(db, student.id, section.id)

    response = await client.post(
        f"/api/v1/attendance/{section.id}",
        json={
            "date": "2025-10-01",
            "entries": [{"student_id": student.id, "status": AttendanceStatus.PRESENT}],
        },
        headers=auth(lecturer),
    )
    assert response.status_code == 201
    data = response.json()
    assert "message" in data


@pytest.mark.asyncio
async def test_mark_attendance_not_your_section(client, db, lecturer, student, section):
    await create_enrollment(db, student.id, section.id)

    # Create another lecturer who does not own this section
    other_lecturer = await make_user(db, "att_other_lect@test.edu", "att_other_lect", UserRole.LECTURER)

    response = await client.post(
        f"/api/v1/attendance/{section.id}",
        json={
            "date": "2025-10-02",
            "entries": [{"student_id": student.id, "status": AttendanceStatus.PRESENT}],
        },
        headers=auth(other_lecturer),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_mark_attendance_updates_existing(client, db, lecturer, student, section):
    await create_enrollment(db, student.id, section.id)
    attendance_date = "2025-10-03"

    # First POST — mark as ABSENT
    await client.post(
        f"/api/v1/attendance/{section.id}",
        json={
            "date": attendance_date,
            "entries": [{"student_id": student.id, "status": AttendanceStatus.ABSENT}],
        },
        headers=auth(lecturer),
    )

    # Second POST on same date — upsert with PRESENT
    response = await client.post(
        f"/api/v1/attendance/{section.id}",
        json={
            "date": attendance_date,
            "entries": [{"student_id": student.id, "status": AttendanceStatus.PRESENT}],
        },
        headers=auth(lecturer),
    )
    assert response.status_code == 201

    # Verify only one AttendanceRecord exists for this date + section
    from sqlalchemy import select
    records_result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.section_id == section.id,
            AttendanceRecord.date == date(2025, 10, 3),
        )
    )
    records = records_result.scalars().all()
    assert len(records) == 1

    # And only one entry (with status PRESENT after upsert)
    entries_result = await db.execute(
        select(AttendanceEntry).where(AttendanceEntry.record_id == records[0].id)
    )
    entries = entries_result.scalars().all()
    assert len(entries) == 1
    assert entries[0].status == AttendanceStatus.PRESENT


@pytest.mark.asyncio
async def test_attendance_summary(client, db, lecturer, student, section):
    await create_enrollment(db, student.id, section.id)

    # Mark one class with the student present
    await client.post(
        f"/api/v1/attendance/{section.id}",
        json={
            "date": "2025-10-04",
            "entries": [{"student_id": student.id, "status": AttendanceStatus.PRESENT}],
        },
        headers=auth(lecturer),
    )

    response = await client.get(
        f"/api/v1/attendance/{section.id}/summary",
        headers=auth(lecturer),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    summary = data[0]
    assert summary["student_id"] == student.id
    assert "percentage" in summary
    assert summary["total_classes"] == 1
    assert summary["attended"] == 1
    assert summary["percentage"] == 100.0
    assert summary["below_threshold"] is False


@pytest.mark.asyncio
async def test_attendance_summary_flags_below_threshold(client, db, lecturer, student, section):
    await create_enrollment(db, student.id, section.id)

    # 2 classes: student present for 1, absent for 1 → 50% < 75% threshold
    await client.post(
        f"/api/v1/attendance/{section.id}",
        json={
            "date": "2025-10-05",
            "entries": [{"student_id": student.id, "status": AttendanceStatus.PRESENT}],
        },
        headers=auth(lecturer),
    )
    await client.post(
        f"/api/v1/attendance/{section.id}",
        json={
            "date": "2025-10-06",
            "entries": [{"student_id": student.id, "status": AttendanceStatus.ABSENT}],
        },
        headers=auth(lecturer),
    )

    response = await client.get(
        f"/api/v1/attendance/{section.id}/summary",
        headers=auth(lecturer),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    summary = data[0]
    assert summary["total_classes"] == 2
    assert summary["attended"] == 1
    assert summary["percentage"] == 50.0
    assert summary["below_threshold"] is True


@pytest.mark.asyncio
async def test_my_attendance(client, db, lecturer, student_user, student, section):
    await create_enrollment(db, student.id, section.id)

    # Mark the student present for one class
    await client.post(
        f"/api/v1/attendance/{section.id}",
        json={
            "date": "2025-10-07",
            "entries": [{"student_id": student.id, "status": AttendanceStatus.PRESENT}],
        },
        headers=auth(lecturer),
    )

    response = await client.get("/api/v1/attendance/my", headers=auth(student_user))
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    record = data[0]
    assert record["section_id"] == section.id
    assert record["total_classes"] == 1
    assert record["attended"] == 1
    assert record["percentage"] == 100.0
    assert "below_threshold" in record
