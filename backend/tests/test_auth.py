"""
Tests for /api/v1/auth endpoints.
"""
import pytest
from tests.conftest import make_user, auth, token_for
from app.models.user import UserRole


@pytest.mark.asyncio
async def test_login_success(client, db):
    user = await make_user(db, "login_ok@test.edu", "login_ok", UserRole.STUDENT)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Password123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 0


@pytest.mark.asyncio
async def test_login_wrong_password(client, db):
    user = await make_user(db, "wrong_pw@test.edu", "wrong_pw", UserRole.STUDENT)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "WrongPassword!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client, db):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@nowhere.edu", "password": "Password123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_without_cookie(client, db):
    # No refresh_token cookie set — should be rejected
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client, db):
    user = await make_user(db, "logout@test.edu", "logout_user", UserRole.STUDENT)
    # Login first so there is a session cookie to clear
    await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Password123!"},
    )
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


@pytest.mark.asyncio
async def test_protected_endpoint_no_token(client, db):
    # Students list requires authentication; no Authorization header sent
    response = await client.get("/api/v1/students")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_bad_token(client, db):
    response = await client.get(
        "/api/v1/students",
        headers={"Authorization": "Bearer this.is.not.a.valid.token"},
    )
    assert response.status_code == 401
