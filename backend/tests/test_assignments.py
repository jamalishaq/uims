"""
Tests for /api/v1/assignments endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta
from tests.conftest import auth, make_user
from app.models.user import UserRole
from app.models.course import CourseEnrollment, CourseSection
from app.models.student import Student, StudentStatus
from app.models.assignment import Assignment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def create_enrollment(db, student_id, section_id):
    e = CourseEnrollment(student_id=student_id, section_id=section_id)
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return e


def future_due_date() -> str:
    """ISO-formatted datetime one week from now."""
    return (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()


def past_due_date() -> str:
    """ISO-formatted datetime one week in the past."""
    return (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_assignment_as_lecturer(client, lecturer, section):
    response = await client.post(
        "/api/v1/assignments",
        json={
            "section_id": section.id,
            "title": "Week 1 Assignment",
            "description": "Complete exercises 1-5",
            "due_date": future_due_date(),
            "max_score": 100.0,
        },
        headers=auth(lecturer),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Week 1 Assignment"
    assert data["section_id"] == section.id
    assert "id" in data


@pytest.mark.asyncio
async def test_create_assignment_not_your_section(client, db, section):
    # Create a different lecturer who does not own this section
    other_lecturer = await make_user(db, "asgn_other_lect@test.edu", "asgn_other_lect", UserRole.LECTURER)

    response = await client.post(
        "/api/v1/assignments",
        json={
            "section_id": section.id,
            "title": "Unauthorized Assignment",
            "due_date": future_due_date(),
            "max_score": 50.0,
        },
        headers=auth(other_lecturer),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_assignments_as_lecturer(client, db, lecturer, section):
    # Create an assignment directly in DB
    assignment = Assignment(
        section_id=section.id,
        title="Lecture Assignment",
        due_date=datetime.now(timezone.utc) + timedelta(days=5),
        max_score=100.0,
    )
    db.add(assignment)
    await db.commit()

    response = await client.get(
        f"/api/v1/assignments?section_id={section.id}",
        headers=auth(lecturer),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(a["title"] == "Lecture Assignment" for a in data)


@pytest.mark.asyncio
async def test_list_assignments_as_enrolled_student(client, db, student_user, student, section, lecturer):
    await create_enrollment(db, student.id, section.id)

    # Create an assignment
    assignment = Assignment(
        section_id=section.id,
        title="Student Visible Assignment",
        due_date=datetime.now(timezone.utc) + timedelta(days=5),
        max_score=100.0,
    )
    db.add(assignment)
    await db.commit()

    response = await client.get(
        f"/api/v1/assignments?section_id={section.id}",
        headers=auth(student_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(a["title"] == "Student Visible Assignment" for a in data)


@pytest.mark.asyncio
async def test_list_assignments_unenrolled_student(client, student_user, student, section):
    # Student has no enrollment in this section
    response = await client.get(
        f"/api/v1/assignments?section_id={section.id}",
        headers=auth(student_user),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_submit_assignment(client, db, student_user, student, section):
    await create_enrollment(db, student.id, section.id)

    assignment = Assignment(
        section_id=section.id,
        title="Submittable Assignment",
        due_date=datetime.now(timezone.utc) + timedelta(days=3),
        max_score=100.0,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    response = await client.post(
        f"/api/v1/assignments/{assignment.id}/submit",
        json={"file_url": "https://example.com/submission.pdf"},
        headers=auth(student_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["assignment_id"] == assignment.id
    assert data["student_id"] == student.id
    assert data["is_late"] is False


@pytest.mark.asyncio
async def test_submit_assignment_unenrolled(client, db, student_user, student, section):
    # No enrollment created — submission should be rejected
    assignment = Assignment(
        section_id=section.id,
        title="Restricted Assignment",
        due_date=datetime.now(timezone.utc) + timedelta(days=3),
        max_score=100.0,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    response = await client.post(
        f"/api/v1/assignments/{assignment.id}/submit",
        json={"file_url": "https://example.com/submission.pdf"},
        headers=auth(student_user),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_submit_late(client, db, student_user, student, section):
    await create_enrollment(db, student.id, section.id)

    # Due date is in the past
    assignment = Assignment(
        section_id=section.id,
        title="Late Assignment",
        due_date=datetime.now(timezone.utc) - timedelta(days=1),
        max_score=100.0,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    response = await client.post(
        f"/api/v1/assignments/{assignment.id}/submit",
        json={"file_url": "https://example.com/late_submission.pdf"},
        headers=auth(student_user),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_late"] is True


@pytest.mark.asyncio
async def test_grade_submission(client, db, lecturer, student_user, student, section):
    await create_enrollment(db, student.id, section.id)

    assignment = Assignment(
        section_id=section.id,
        title="Gradeable Assignment",
        due_date=datetime.now(timezone.utc) + timedelta(days=5),
        max_score=50.0,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    # Student submits
    submit_resp = await client.post(
        f"/api/v1/assignments/{assignment.id}/submit",
        json={"file_url": "https://example.com/work.pdf"},
        headers=auth(student_user),
    )
    submission_id = submit_resp.json()["id"]

    # Lecturer grades it
    response = await client.post(
        f"/api/v1/assignments/{assignment.id}/submissions/{submission_id}/grade",
        json={"score": 45.0, "feedback": "Good work"},
        headers=auth(lecturer),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 45.0
    assert data["feedback"] == "Good work"


@pytest.mark.asyncio
async def test_grade_over_max(client, db, lecturer, student_user, student, section):
    await create_enrollment(db, student.id, section.id)

    assignment = Assignment(
        section_id=section.id,
        title="Max Score Assignment",
        due_date=datetime.now(timezone.utc) + timedelta(days=5),
        max_score=50.0,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    # Student submits
    submit_resp = await client.post(
        f"/api/v1/assignments/{assignment.id}/submit",
        json={"file_url": "https://example.com/work.pdf"},
        headers=auth(student_user),
    )
    submission_id = submit_resp.json()["id"]

    # Score 75 exceeds max_score of 50 — should return 400
    response = await client.post(
        f"/api/v1/assignments/{assignment.id}/submissions/{submission_id}/grade",
        json={"score": 75.0},
        headers=auth(lecturer),
    )
    assert response.status_code == 400
