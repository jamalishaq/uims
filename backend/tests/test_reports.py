"""Tests for the reports router: /api/v1/reports/"""
import pytest
from tests.conftest import auth
from app.models.course import CourseEnrollment
from app.models.payment import Payment, FeeType, PaymentStatus


# ---------------------------------------------------------------------------
# GET /reports/enrollment-stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enrollment_stats_empty(client, admin):
    response = await client.get(
        "/api/v1/reports/enrollment-stats",
        headers=auth(admin),
    )
    assert response.status_code == 200
    # No enrollments in a clean DB
    assert response.json() == []


@pytest.mark.asyncio
async def test_enrollment_stats_with_data(client, db, admin, student, section):
    # Enroll the student in the section
    enrollment = CourseEnrollment(
        student_id=student.id,
        section_id=section.id,
    )
    db.add(enrollment)
    await db.commit()

    response = await client.get(
        f"/api/v1/reports/enrollment-stats?semester_id={section.semester_id}",
        headers=auth(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    row = data[0]
    assert "program_id" in row
    assert "program_name" in row
    assert "level" in row
    assert "student_count" in row
    assert row["student_count"] >= 1


# ---------------------------------------------------------------------------
# GET /reports/pass-fail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pass_fail_empty(client, admin):
    response = await client.get(
        "/api/v1/reports/pass-fail",
        headers=auth(admin),
    )
    assert response.status_code == 200
    # No graded enrollments → empty list
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET /reports/fee-collection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fee_collection_empty(client, admin):
    response = await client.get(
        "/api/v1/reports/fee-collection",
        headers=auth(admin),
    )
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET /reports/cgpa-distribution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cgpa_distribution(client, admin):
    response = await client.get(
        "/api/v1/reports/cgpa-distribution",
        headers=auth(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Always returns exactly 5 buckets regardless of data
    assert len(data) == 5
    ranges = [item["range"] for item in data]
    assert "0.0–1.0" in ranges
    assert "4.0–5.0" in ranges
    for item in data:
        assert "range" in item
        assert "count" in item


# ---------------------------------------------------------------------------
# Forbidden access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reports_forbidden_for_student(client, student_user):
    response = await client.get(
        "/api/v1/reports/enrollment-stats",
        headers=auth(student_user),
    )
    assert response.status_code == 403
