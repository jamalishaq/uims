"""Tests for the payments router: /api/v1/payments/"""
import pytest
from unittest.mock import patch, AsyncMock
from tests.conftest import auth
from app.models.payment import FeeSchedule, FeeType, Payment, PaymentStatus


# ---------------------------------------------------------------------------
# POST /payments/schedule
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_fee_schedule_as_bursar(client, bursar, semester):
    payload = {
        "semester_id": semester.id,
        "fee_type": FeeType.TUITION,
        "amount": 150000.0,
    }
    response = await client.post(
        "/api/v1/payments/schedule",
        json=payload,
        headers=auth(bursar),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["semester_id"] == semester.id
    assert data["fee_type"] == FeeType.TUITION
    assert data["amount"] == 150000.0


@pytest.mark.asyncio
async def test_create_fee_schedule_as_student(client, student_user, semester):
    payload = {
        "semester_id": semester.id,
        "fee_type": FeeType.TUITION,
        "amount": 150000.0,
    }
    response = await client.post(
        "/api/v1/payments/schedule",
        json=payload,
        headers=auth(student_user),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /payments/schedule
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_fee_schedule_current_semester(client, db, semester):
    # Create a schedule for the current semester (is_current=True via fixture)
    schedule = FeeSchedule(
        semester_id=semester.id,
        fee_type=FeeType.LIBRARY,
        amount=5000.0,
    )
    db.add(schedule)
    await db.commit()

    # No semester_id param — should use current semester
    response = await client.get("/api/v1/payments/schedule")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(item["fee_type"] == FeeType.LIBRARY for item in data)


@pytest.mark.asyncio
async def test_get_fee_schedule_by_semester_id(client, db, semester):
    schedule = FeeSchedule(
        semester_id=semester.id,
        fee_type=FeeType.EXAM,
        amount=10000.0,
    )
    db.add(schedule)
    await db.commit()

    response = await client.get(f"/api/v1/payments/schedule?semester_id={semester.id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(item["semester_id"] == semester.id for item in data)


# ---------------------------------------------------------------------------
# POST /payments/generate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_payments(client, db, bursar, student, semester):
    # Create a fee schedule for the semester
    schedule = FeeSchedule(
        semester_id=semester.id,
        fee_type=FeeType.TUITION,
        amount=200000.0,
    )
    db.add(schedule)
    await db.commit()

    response = await client.post(
        f"/api/v1/payments/generate?student_id={student.id}&semester_id={semester.id}",
        headers=auth(bursar),
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["student_id"] == student.id
    assert data[0]["fee_type"] == FeeType.TUITION
    assert data[0]["amount_due"] == 200000.0
    assert data[0]["status"] == PaymentStatus.PENDING


@pytest.mark.asyncio
async def test_generate_payments_skips_existing(client, db, bursar, student, semester):
    # Create the fee schedule
    schedule = FeeSchedule(
        semester_id=semester.id,
        fee_type=FeeType.ACCOMMODATION,
        amount=50000.0,
    )
    db.add(schedule)
    await db.commit()

    # First generation
    r1 = await client.post(
        f"/api/v1/payments/generate?student_id={student.id}&semester_id={semester.id}",
        headers=auth(bursar),
    )
    assert r1.status_code == 200
    first_count = len(r1.json())

    # Second generation — should return empty list (no new payments created)
    r2 = await client.post(
        f"/api/v1/payments/generate?student_id={student.id}&semester_id={semester.id}",
        headers=auth(bursar),
    )
    assert r2.status_code == 200
    assert len(r2.json()) == 0  # duplicates skipped


# ---------------------------------------------------------------------------
# GET /payments/my
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_my_payments_empty(client, student_user, student):
    response = await client.get("/api/v1/payments/my", headers=auth(student_user))
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_my_payments_after_generate(client, db, bursar, student_user, student, semester):
    # Seed a fee schedule and generate payments
    schedule = FeeSchedule(
        semester_id=semester.id,
        fee_type=FeeType.DEPARTMENT,
        amount=8000.0,
    )
    db.add(schedule)
    await db.commit()

    await client.post(
        f"/api/v1/payments/generate?student_id={student.id}&semester_id={semester.id}",
        headers=auth(bursar),
    )

    response = await client.get("/api/v1/payments/my", headers=auth(student_user))
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["student_id"] == student.id


# ---------------------------------------------------------------------------
# POST /payments/initialize
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_payment(client, db, student_user, student, semester):
    # Seed a pending payment record
    payment = Payment(
        student_id=student.id,
        semester_id=semester.id,
        fee_type=FeeType.TUITION,
        amount_due=100000.0,
        amount_paid=0.0,
        balance=100000.0,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    mock_result = {
        "authorization_url": "https://paystack.com/pay/test",
        "reference": "ref123",
    }

    # Patch the name as it was imported into the router module
    with patch(
        "app.routers.payments.initialize_transaction",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = await client.post(
            f"/api/v1/payments/initialize?payment_id={payment.id}",
            headers=auth(student_user),
        )

    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "reference" in data
