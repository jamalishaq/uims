"""
Tests for /api/v1/enrollment endpoints.
"""
import pytest
from tests.conftest import auth, make_user
from app.models.user import UserRole
from app.models.course import CourseEnrollment, EnrollmentStatus


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
async def test_my_enrollments_empty(client, student_user, student):
    # Student has no enrollments yet — should return an empty list
    response = await client.get("/api/v1/enrollment", headers=auth(student_user))
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_my_enrollments_returns_enrolled(client, db, student_user, student, section):
    await create_enrollment(db, student.id, section.id)

    response = await client.get("/api/v1/enrollment", headers=auth(student_user))
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["section_id"] == section.id
    assert data[0]["status"] == EnrollmentStatus.REGISTERED


@pytest.mark.asyncio
async def test_enroll_success(client, student_user, student, section):
    response = await client.post(
        "/api/v1/enrollment",
        json={"section_id": section.id},
        headers=auth(student_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert "message" in data


@pytest.mark.asyncio
async def test_enroll_duplicate(client, db, student_user, student, section):
    # First enrollment created directly in DB
    await create_enrollment(db, student.id, section.id)

    # Attempt to enroll again via API should return 400
    response = await client.post(
        "/api/v1/enrollment",
        json={"section_id": section.id},
        headers=auth(student_user),
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_enroll_as_non_student(client, lecturer, section):
    # Lecturer role is not allowed to enroll
    response = await client.post(
        "/api/v1/enrollment",
        json={"section_id": section.id},
        headers=auth(lecturer),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_drop_course(client, db, student_user, student, section):
    enrollment = await create_enrollment(db, student.id, section.id)

    response = await client.delete(
        f"/api/v1/enrollment/{enrollment.id}",
        headers=auth(student_user),
    )
    assert response.status_code == 200

    # Verify status changed to DROPPED
    await db.refresh(enrollment)
    assert enrollment.status == EnrollmentStatus.DROPPED


@pytest.mark.asyncio
async def test_drop_others_enrollment(client, db, student_user, student, section, program):
    # Create another student and enroll them
    other_user = await make_user(db, "other_student@test.edu", "other_student", UserRole.STUDENT)
    from app.models.student import Student, StudentStatus
    other_student = Student(
        user_id=other_user.id,
        matric_number="BSCCSC-2025-0099",
        program_id=program.id,
        level=100,
        status=StudentStatus.ACTIVE,
    )
    db.add(other_student)
    await db.commit()
    await db.refresh(other_student)

    other_enrollment = await create_enrollment(db, other_student.id, section.id)

    # student_user tries to drop other student's enrollment — should get 404
    response = await client.delete(
        f"/api/v1/enrollment/{other_enrollment.id}",
        headers=auth(student_user),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_section_roster(client, db, lecturer, student, section):
    await create_enrollment(db, student.id, section.id)

    response = await client.get(
        f"/api/v1/enrollment/section/{section.id}",
        headers=auth(lecturer),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["student_id"] == student.id
