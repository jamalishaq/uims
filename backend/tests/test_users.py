"""Tests for the users router: /api/v1/users/"""
import pytest
from tests.conftest import auth, make_user
from app.models.user import UserRole


# ---------------------------------------------------------------------------
# GET /users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_users_as_admin(client, admin, student_user):
    response = await client.get("/api/v1/users", headers=auth(admin))
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Each item should have the expected shape
    first = data[0]
    assert "id" in first
    assert "email" in first
    assert "username" in first
    assert "role" in first
    assert "is_active" in first


@pytest.mark.asyncio
async def test_list_users_filter_by_role(client, admin, student_user):
    response = await client.get(
        f"/api/v1/users?role={UserRole.STUDENT}",
        headers=auth(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # All returned users must have the student role
    assert all(u["role"] == UserRole.STUDENT for u in data)


@pytest.mark.asyncio
async def test_list_users_as_non_admin(client, registrar, lecturer):
    # Registrar should not be able to list users
    r_registrar = await client.get("/api/v1/users", headers=auth(registrar))
    assert r_registrar.status_code == 403

    # Lecturer should not be able to list users
    r_lecturer = await client.get("/api/v1/users", headers=auth(lecturer))
    assert r_lecturer.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /users/{id}/toggle-active
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_toggle_active_deactivates(client, db, admin, lecturer):
    assert lecturer.is_active is True

    response = await client.patch(
        f"/api/v1/users/{lecturer.id}/toggle-active",
        headers=auth(admin),
    )
    assert response.status_code == 200

    await db.refresh(lecturer)
    assert lecturer.is_active is False


@pytest.mark.asyncio
async def test_toggle_active_reactivates(client, db, admin, lecturer):
    # Manually deactivate first
    lecturer.is_active = False
    await db.commit()

    response = await client.patch(
        f"/api/v1/users/{lecturer.id}/toggle-active",
        headers=auth(admin),
    )
    assert response.status_code == 200

    await db.refresh(lecturer)
    assert lecturer.is_active is True


@pytest.mark.asyncio
async def test_toggle_own_account(client, admin):
    response = await client.patch(
        f"/api/v1/users/{admin.id}/toggle-active",
        headers=auth(admin),
    )
    assert response.status_code == 400
    assert "own account" in response.json()["detail"].lower()
