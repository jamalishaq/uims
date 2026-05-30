"""Tests for the students router: /api/v1/students/"""
import pytest
from tests.conftest import auth, make_user
from app.models.user import UserRole
from app.models.student import Student, StudentStatus


# ---------------------------------------------------------------------------
# GET /students
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_students_as_admin(client, admin, student):
    response = await client.get("/api/v1/students", headers=auth(admin))
    assert response.status_code == 200
    data = response.json()
    # Paginated response shape
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "pages" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_students_as_student(client, student_user, student):
    response = await client.get("/api/v1/students", headers=auth(student_user))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_students_search_by_matric(client, admin, student):
    # Search by the full matric number — should return exactly this student
    matric = student.matric_number
    response = await client.get(
        f"/api/v1/students?q={matric}",
        headers=auth(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(item["matric_number"] == matric for item in data["items"])


# ---------------------------------------------------------------------------
# GET /students/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_student_detail(client, admin, student):
    response = await client.get(
        f"/api/v1/students/{student.id}",
        headers=auth(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == student.id
    assert data["matric_number"] == student.matric_number
    assert "username" in data
    assert "email" in data


@pytest.mark.asyncio
async def test_get_student_not_found(client, admin):
    response = await client.get(
        "/api/v1/students/999999",
        headers=auth(admin),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /students/me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_my_student_record(client, student_user, student):
    response = await client.get("/api/v1/students/me", headers=auth(student_user))
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == student_user.id
    assert data["matric_number"] == student.matric_number
    assert data["username"] == student_user.username
    assert data["email"] == student_user.email


# ---------------------------------------------------------------------------
# PATCH /students/{id}/status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_student_status(client, db, registrar, student):
    response = await client.patch(
        f"/api/v1/students/{student.id}/status",
        json={"status": StudentStatus.ON_LEAVE},
        headers=auth(registrar),
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data

    await db.refresh(student)
    assert student.status == StudentStatus.ON_LEAVE


@pytest.mark.asyncio
async def test_update_student_status_as_lecturer(client, lecturer, student):
    response = await client.patch(
        f"/api/v1/students/{student.id}/status",
        json={"status": StudentStatus.SUSPENDED},
        headers=auth(lecturer),
    )
    assert response.status_code == 403
