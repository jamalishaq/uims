"""
Tests for /api/v1/grades endpoints.
"""
import pytest
from tests.conftest import auth, make_user
from app.models.user import UserRole
from app.models.course import CourseEnrollment, EnrollmentStatus
from app.models.student import Student, StudentStatus


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
async def test_submit_grade_success(client, db, lecturer, student, section, grade_scale):
    enrollment = await create_enrollment(db, student.id, section.id)

    response = await client.post(
        f"/api/v1/grades/{enrollment.id}",
        json={"ca_score": 35.0, "exam_score": 50.0},
        headers=auth(lecturer),
    )
    assert response.status_code == 200
    data = response.json()
    assert "grade" in data
    assert "grade_points" in data
    assert "passed" in data


@pytest.mark.asyncio
async def test_submit_grade_not_your_section(client, db, lecturer, student, section, grade_scale, program):
    enrollment = await create_enrollment(db, student.id, section.id)

    # Create a second lecturer who does not own this section
    other_lecturer = await make_user(db, "other_lecturer@test.edu", "other_lecturer", UserRole.LECTURER)

    response = await client.post(
        f"/api/v1/grades/{enrollment.id}",
        json={"ca_score": 30.0, "exam_score": 45.0},
        headers=auth(other_lecturer),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_submit_grade_ca_over_limit(client, db, lecturer, student, section, grade_scale):
    enrollment = await create_enrollment(db, student.id, section.id)

    # ca_score=45 exceeds the Field(le=40) constraint — Pydantic rejects with 422
    response = await client.post(
        f"/api/v1/grades/{enrollment.id}",
        json={"ca_score": 45.0, "exam_score": 50.0},
        headers=auth(lecturer),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_transcript_empty(client, db, student_user, student, admin):
    # No graded enrollments — courses list should be empty
    response = await client.get(
        f"/api/v1/grades/transcript/{student.id}",
        headers=auth(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["student_id"] == student.id
    assert data["courses"] == []


@pytest.mark.asyncio
async def test_transcript_after_grading(client, db, lecturer, student_user, student, section, grade_scale, admin):
    enrollment = await create_enrollment(db, student.id, section.id)

    # Submit a grade for the enrollment
    await client.post(
        f"/api/v1/grades/{enrollment.id}",
        json={"ca_score": 30.0, "exam_score": 50.0},
        headers=auth(lecturer),
    )

    # Transcript should now include the graded course
    response = await client.get(
        f"/api/v1/grades/transcript/{student.id}",
        headers=auth(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["courses"]) == 1
    assert data["courses"][0]["grade"] is not None


@pytest.mark.asyncio
async def test_transcript_student_can_only_see_own(client, db, student_user, student, program):
    # Create a second student
    other_user = await make_user(db, "other_std@test.edu", "other_std", UserRole.STUDENT)
    other_student = Student(
        user_id=other_user.id,
        matric_number="BSCCSC-2025-0088",
        program_id=program.id,
        level=100,
        status=StudentStatus.ACTIVE,
    )
    db.add(other_student)
    await db.commit()
    await db.refresh(other_student)

    # student_user tries to view other_student's transcript — should be 403
    response = await client.get(
        f"/api/v1/grades/transcript/{other_student.id}",
        headers=auth(student_user),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_my_grades(client, db, student_user, student, section):
    await create_enrollment(db, student.id, section.id)

    response = await client.get("/api/v1/grades/me", headers=auth(student_user))
    assert response.status_code == 200
    data = response.json()
    assert data["student_id"] == student.id
    assert "courses" in data
    assert isinstance(data["courses"], list)
    assert len(data["courses"]) == 1


@pytest.mark.asyncio
async def test_section_grades_as_lecturer(client, db, lecturer, student, section):
    await create_enrollment(db, student.id, section.id)

    response = await client.get(
        f"/api/v1/grades/section/{section.id}",
        headers=auth(lecturer),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["student_id"] == student.id
