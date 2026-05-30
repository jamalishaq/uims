"""
Tests for /api/v1/academic endpoints.
"""
import pytest
from datetime import date
from tests.conftest import auth
from app.models.calendar import SemesterName
from app.models.academic import DegreeType


# ---------------------------------------------------------------------------
# Faculties
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_faculties_empty(client, admin):
    # No faculty fixture injected — list should be empty
    response = await client.get("/api/v1/academic/faculties", headers=auth(admin))
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_faculty_as_admin(client, admin):
    response = await client.post(
        "/api/v1/academic/faculties",
        json={"name": "Faculty of Engineering", "code": "ENG"},
        headers=auth(admin),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Faculty of Engineering"
    assert data["code"] == "ENG"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_faculty_as_non_admin(client, registrar):
    response = await client.post(
        "/api/v1/academic/faculties",
        json={"name": "Faculty of Arts", "code": "ART"},
        headers=auth(registrar),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_faculties_after_create(client, admin, faculty):
    # `faculty` fixture inserts "Faculty of Science" / "SCI"
    response = await client.get("/api/v1/academic/faculties", headers=auth(admin))
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    codes = [f["code"] for f in data]
    assert "SCI" in codes


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_department(client, admin, faculty):
    response = await client.post(
        "/api/v1/academic/departments",
        json={"name": "Mathematics", "code": "MTH", "faculty_id": faculty.id},
        headers=auth(admin),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Mathematics"
    assert data["faculty_id"] == faculty.id


@pytest.mark.asyncio
async def test_list_departments_filter_by_faculty(client, admin, department, faculty):
    # `department` fixture creates "Computer Science" under `faculty`
    response = await client.get(
        f"/api/v1/academic/departments?faculty_id={faculty.id}",
        headers=auth(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for dept in data:
        assert dept["faculty_id"] == faculty.id


# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_program(client, admin, department):
    response = await client.post(
        "/api/v1/academic/programs",
        json={
            "name": "B.Sc Mathematics",
            "code": "BSCMTH",
            "department_id": department.id,
            "degree_type": DegreeType.BSC.value,
            "duration_years": 4,
            "total_credits_required": 120,
            "core_credits_required": 90,
            "elective_credits_required": 30,
        },
        headers=auth(admin),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "B.Sc Mathematics"
    assert data["department_id"] == department.id
    assert data["degree_type"] == DegreeType.BSC.value


@pytest.mark.asyncio
async def test_list_programs_filter_by_department(client, admin, program, department):
    # `program` fixture creates "B.Sc Computer Science" under `department`
    response = await client.get(
        f"/api/v1/academic/programs?department_id={department.id}",
        headers=auth(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for prog in data:
        assert prog["department_id"] == department.id


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_session(client, admin):
    response = await client.post(
        "/api/v1/academic/sessions",
        json={
            "name": "2026/2027",
            "start_date": "2026-09-01",
            "end_date": "2027-06-30",
            "is_current": False,
        },
        headers=auth(admin),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "2026/2027"
    assert data["is_current"] is False


@pytest.mark.asyncio
async def test_create_session_is_current_deactivates_others(client, admin, session):
    # `session` fixture creates one is_current=True session
    # Creating a new is_current session should flip the old one to False
    response = await client.post(
        "/api/v1/academic/sessions",
        json={
            "name": "2027/2028",
            "start_date": "2027-09-01",
            "end_date": "2028-06-30",
            "is_current": True,
        },
        headers=auth(admin),
    )
    assert response.status_code == 201
    new_session = response.json()
    assert new_session["is_current"] is True

    # List all sessions and verify only the new one is current
    list_resp = await client.get("/api/v1/academic/sessions", headers=auth(admin))
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    current_sessions = [s for s in sessions if s["is_current"]]
    assert len(current_sessions) == 1
    assert current_sessions[0]["name"] == "2027/2028"


@pytest.mark.asyncio
async def test_create_semester(client, admin, session):
    response = await client.post(
        f"/api/v1/academic/sessions/{session.id}/semesters",
        json={
            "name": SemesterName.SECOND.value,
            "start_date": "2026-02-01",
            "end_date": "2026-06-30",
            "registration_start": "2026-01-15",
            "registration_end": "2026-02-15",
            "is_current": False,
        },
        headers=auth(admin),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["session_id"] == session.id
    assert data["name"] == SemesterName.SECOND.value


@pytest.mark.asyncio
async def test_create_semester_invalid_session(client, admin):
    response = await client.post(
        "/api/v1/academic/sessions/999999/semesters",
        json={
            "name": SemesterName.FIRST.value,
            "start_date": "2026-09-01",
            "end_date": "2027-01-31",
            "registration_start": "2026-08-15",
            "registration_end": "2026-09-15",
            "is_current": False,
        },
        headers=auth(admin),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# HOD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_my_department_no_dept(client, hod_user):
    # hod_user exists but no Department has hod_id set to this user
    response = await client.get(
        "/api/v1/academic/my-department",
        headers=auth(hod_user),
    )
    assert response.status_code == 404
