"""Tests for the admission router: /api/v1/admission/"""
import pytest
from tests.conftest import auth, make_user
from app.models.admission import Application, ApplicationStatus
from app.models.user import UserRole


APPLY_PAYLOAD = {
    "first_name": "Jane",
    "last_name": "Doe",
    "phone": "08012345678",
    "address": "123 Test Street, Lagos",
    "date_of_birth": "1999-03-15",
}


# ---------------------------------------------------------------------------
# POST /admission/apply
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_success(client, applicant, program, session):
    payload = {**APPLY_PAYLOAD, "program_id": program.id, "session_id": session.id}
    response = await client.post(
        "/api/v1/admission/apply",
        json=payload,
        headers=auth(applicant),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == applicant.id
    assert data["program_id"] == program.id
    assert data["session_id"] == session.id
    assert data["status"] == ApplicationStatus.SUBMITTED
    assert data["first_name"] == "Jane"
    assert data["last_name"] == "Doe"


@pytest.mark.asyncio
async def test_apply_duplicate(client, applicant, program, session):
    payload = {**APPLY_PAYLOAD, "program_id": program.id, "session_id": session.id}
    # First application should succeed
    r1 = await client.post(
        "/api/v1/admission/apply", json=payload, headers=auth(applicant)
    )
    assert r1.status_code == 201

    # Second identical application should be rejected
    r2 = await client.post(
        "/api/v1/admission/apply", json=payload, headers=auth(applicant)
    )
    assert r2.status_code == 400
    assert "already submitted" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_apply_as_non_applicant(client, student_user, admin, program, session):
    payload = {**APPLY_PAYLOAD, "program_id": program.id, "session_id": session.id}

    # student_user role=STUDENT → should get 403
    r_student = await client.post(
        "/api/v1/admission/apply", json=payload, headers=auth(student_user)
    )
    assert r_student.status_code == 403

    # admin role=SUPER_ADMIN → should get 403 (not an applicant)
    r_admin = await client.post(
        "/api/v1/admission/apply", json=payload, headers=auth(admin)
    )
    assert r_admin.status_code == 403


# ---------------------------------------------------------------------------
# GET /admission/applications
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_applications_as_registrar(client, db, registrar, applicant, program, session):
    # Create an application directly in DB
    app_obj = Application(
        user_id=applicant.id,
        program_id=program.id,
        session_id=session.id,
        status=ApplicationStatus.SUBMITTED,
        first_name="John",
        last_name="Smith",
        phone="08011111111",
        address="10 Test Ave",
        date_of_birth="2000-01-01",
    )
    db.add(app_obj)
    await db.commit()

    response = await client.get(
        "/api/v1/admission/applications", headers=auth(registrar)
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_applications_filter_by_status(client, db, registrar, applicant, program, session):
    # Create a SUBMITTED and a REJECTED application
    submitted = Application(
        user_id=applicant.id,
        program_id=program.id,
        session_id=session.id,
        status=ApplicationStatus.SUBMITTED,
        first_name="Sub",
        last_name="Mitted",
        phone="08022222222",
        address="Addr 1",
        date_of_birth="1998-06-10",
    )
    rejected = Application(
        user_id=applicant.id,
        program_id=program.id,
        session_id=session.id,
        status=ApplicationStatus.REJECTED,
        first_name="Re",
        last_name="Jected",
        phone="08033333333",
        address="Addr 2",
        date_of_birth="1997-07-20",
        rejection_reason="Incomplete docs",
    )
    db.add(submitted)
    db.add(rejected)
    await db.commit()

    response = await client.get(
        "/api/v1/admission/applications?app_status=submitted",
        headers=auth(registrar),
    )
    assert response.status_code == 200
    results = response.json()
    assert all(r["status"] == ApplicationStatus.SUBMITTED for r in results)


@pytest.mark.asyncio
async def test_list_applications_as_student(client, student_user):
    response = await client.get(
        "/api/v1/admission/applications", headers=auth(student_user)
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /admission/applications/{id}/decision
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decision_accept(client, db, registrar, applicant, program, session):
    app_obj = Application(
        user_id=applicant.id,
        program_id=program.id,
        session_id=session.id,
        status=ApplicationStatus.SUBMITTED,
        first_name="Accept",
        last_name="Me",
        phone="08044444444",
        address="Accept Ave",
        date_of_birth="1999-09-09",
    )
    db.add(app_obj)
    await db.commit()
    await db.refresh(app_obj)

    response = await client.post(
        f"/api/v1/admission/applications/{app_obj.id}/decision",
        json={"action": "accept"},
        headers=auth(registrar),
    )
    assert response.status_code == 200

    await db.refresh(app_obj)
    assert app_obj.status == ApplicationStatus.ACCEPTED


@pytest.mark.asyncio
async def test_decision_reject_with_reason(client, db, registrar, applicant, program, session):
    app_obj = Application(
        user_id=applicant.id,
        program_id=program.id,
        session_id=session.id,
        status=ApplicationStatus.SUBMITTED,
        first_name="Reject",
        last_name="Me",
        phone="08055555555",
        address="Reject Road",
        date_of_birth="1998-08-08",
    )
    db.add(app_obj)
    await db.commit()
    await db.refresh(app_obj)

    response = await client.post(
        f"/api/v1/admission/applications/{app_obj.id}/decision",
        json={"action": "reject", "rejection_reason": "Failed screening"},
        headers=auth(registrar),
    )
    assert response.status_code == 200

    await db.refresh(app_obj)
    assert app_obj.status == ApplicationStatus.REJECTED
    assert app_obj.rejection_reason == "Failed screening"


@pytest.mark.asyncio
async def test_decision_invalid_action(client, db, registrar, applicant, program, session):
    app_obj = Application(
        user_id=applicant.id,
        program_id=program.id,
        session_id=session.id,
        status=ApplicationStatus.SUBMITTED,
        first_name="Invalid",
        last_name="Action",
        phone="08066666666",
        address="Maybe Lane",
        date_of_birth="1997-07-07",
    )
    db.add(app_obj)
    await db.commit()
    await db.refresh(app_obj)

    response = await client.post(
        f"/api/v1/admission/applications/{app_obj.id}/decision",
        json={"action": "maybe"},
        headers=auth(registrar),
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /admission/applications/{id}/enroll
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enroll_accepted_applicant(client, db, registrar, applicant, program, session):
    # Create and accept an application
    app_obj = Application(
        user_id=applicant.id,
        program_id=program.id,
        session_id=session.id,
        status=ApplicationStatus.ACCEPTED,
        first_name="Enroll",
        last_name="Me",
        phone="08077777777",
        address="Enroll Estate",
        date_of_birth="2000-02-02",
    )
    db.add(app_obj)
    await db.commit()
    await db.refresh(app_obj)

    response = await client.post(
        f"/api/v1/admission/applications/{app_obj.id}/enroll",
        headers=auth(registrar),
    )
    assert response.status_code == 200
    data = response.json()
    assert "matric_number" in data
    assert "student_id" in data
    assert data["matric_number"].startswith(program.code.upper())

    await db.refresh(app_obj)
    assert app_obj.status == ApplicationStatus.ENROLLED


@pytest.mark.asyncio
async def test_enroll_non_accepted(client, db, registrar, applicant, program, session):
    # Application still in SUBMITTED state — cannot enroll
    app_obj = Application(
        user_id=applicant.id,
        program_id=program.id,
        session_id=session.id,
        status=ApplicationStatus.SUBMITTED,
        first_name="Not",
        last_name="Ready",
        phone="08088888888",
        address="Pending Place",
        date_of_birth="2001-03-03",
    )
    db.add(app_obj)
    await db.commit()
    await db.refresh(app_obj)

    response = await client.post(
        f"/api/v1/admission/applications/{app_obj.id}/enroll",
        headers=auth(registrar),
    )
    assert response.status_code == 400
