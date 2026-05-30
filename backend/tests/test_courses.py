"""
Tests for /api/v1/courses endpoints.
"""
import pytest
from tests.conftest import auth, make_user
from app.models.course import CourseType
from app.models.user import UserRole


# ---------------------------------------------------------------------------
# Courses — list & create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_courses_empty(client, admin):
    # No course fixture injected — list should be empty
    response = await client.get("/api/v1/courses", headers=auth(admin))
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_course_as_admin(client, admin, department):
    response = await client.post(
        "/api/v1/courses",
        json={
            "code": "MTH101",
            "title": "Calculus I",
            "credit_hours": 3,
            "course_type": CourseType.CORE.value,
            "department_id": department.id,
            "description": "Introduction to differential calculus",
        },
        headers=auth(admin),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["code"] == "MTH101"
    assert data["title"] == "Calculus I"
    assert data["department_id"] == department.id
    assert data["prerequisites"] == []


@pytest.mark.asyncio
async def test_create_course_as_student(client, db, department):
    student = await make_user(db, "student_course@test.edu", "student_course", UserRole.STUDENT)
    response = await client.post(
        "/api/v1/courses",
        json={
            "code": "PHY101",
            "title": "Physics I",
            "credit_hours": 3,
            "course_type": CourseType.CORE.value,
            "department_id": department.id,
        },
        headers=auth(student),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Courses — get by ID
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_course_by_id(client, admin, course):
    # `course` fixture creates CSC101
    response = await client.get(f"/api/v1/courses/{course.id}", headers=auth(admin))
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == course.id
    assert data["code"] == "CSC101"
    assert "prerequisites" in data


@pytest.mark.asyncio
async def test_get_course_not_found(client, admin):
    response = await client.get("/api/v1/courses/999999", headers=auth(admin))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_prerequisite(client, admin, department):
    # Create two courses then link them
    r1 = await client.post(
        "/api/v1/courses",
        json={
            "code": "CSC100",
            "title": "Intro to Computers",
            "credit_hours": 2,
            "course_type": CourseType.CORE.value,
            "department_id": department.id,
        },
        headers=auth(admin),
    )
    assert r1.status_code == 201
    prereq_id = r1.json()["id"]

    r2 = await client.post(
        "/api/v1/courses",
        json={
            "code": "CSC200",
            "title": "Data Structures",
            "credit_hours": 3,
            "course_type": CourseType.CORE.value,
            "department_id": department.id,
        },
        headers=auth(admin),
    )
    assert r2.status_code == 201
    course_id = r2.json()["id"]

    response = await client.post(
        f"/api/v1/courses/{course_id}/prerequisites",
        json={"prerequisite_id": prereq_id},
        headers=auth(admin),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["prerequisite_id"] == prereq_id


@pytest.mark.asyncio
async def test_add_self_as_prerequisite(client, admin, course):
    response = await client.post(
        f"/api/v1/courses/{course.id}/prerequisites",
        json={"prerequisite_id": course.id},
        headers=auth(admin),
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Sections — list & create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_sections_empty(client, admin):
    # No section fixture injected — list should be empty
    response = await client.get("/api/v1/courses/sections", headers=auth(admin))
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_section(client, admin, course, semester, lecturer):
    response = await client.post(
        "/api/v1/courses/sections",
        json={
            "course_id": course.id,
            "semester_id": semester.id,
            "lecturer_id": lecturer.id,
            "max_enrollment": 40,
            "venue": "LT2",
            "schedule": "Tue/Thu 10:00-11:30",
        },
        headers=auth(admin),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["course_id"] == course.id
    assert data["semester_id"] == semester.id
    assert data["lecturer_id"] == lecturer.id
    assert data["venue"] == "LT2"


@pytest.mark.asyncio
async def test_list_sections_filter_by_semester(client, admin, section, semester):
    # `section` fixture creates one section linked to `semester`
    response = await client.get(
        f"/api/v1/courses/sections?semester_id={semester.id}",
        headers=auth(admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for s in data:
        assert s["semester_id"] == semester.id
