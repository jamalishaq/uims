"""Enrollment over HTTP: the discriminated outcome, and three cross-context adapters at once.

Registering for a course is the one request in the system that touches four contexts. It asks
Course Catalog what the course requires, Academic Records what the student has passed, and
Billing whether they are cleared — each through a query port answered by an adapter the
composition root wired to a use case in another context. None of those contexts imports either
of the others, so these tests are the only place the three adapters are shown to be connected
to anything at all.

Offerings are seeded through the repository because ``CourseOffering`` has no use case in front
of it — the same application-layer gap Faculty & Department's routes run into.
"""

from datetime import UTC, datetime
from decimal import Decimal

from httpx import AsyncClient

from billing.domain.account import Account
from billing.domain.charge import ChargeKind
from billing.domain.values import Money
from enrollment.domain.course_offering import CourseOffering
from enrollment.domain.values import SemesterOrdinal, Term

TERM = Term(session_id="sess-2026", semester_id="sem-1", ordinal=SemesterOrdinal.FIRST)

REGISTRATION = {
    "enrollment_id": "enr-1",
    "student_id": "stu-1",
    "course_id": "csc101",
    "session_id": "sess-2026",
    "semester_id": "sem-1",
    "semester_ordinal": 1,
}


async def _seed_course(client: AsyncClient, api: str, *, credit_units: int = 3) -> None:
    response = await client.post(
        f"{api}/course-catalog/courses",
        json={
            "course_id": "csc101",
            "department_id": "dept-csc",
            "code": "CSC101",
            "title": "Introduction to Computer Science",
            "credit_units": credit_units,
        },
    )
    assert response.status_code == 201, response.text


async def _seed_offering(repos, *, capacity: int = 30) -> None:
    await repos.offerings().add(CourseOffering.open("csc101", TERM, capacity))


async def _seed_cleared_account(repos, *, paid: str = "100000.00") -> None:
    """A ledger with the session fee raised and settled, so clearance answers yes.

    Seeded rather than driven, because ``OpenAccountForOffer`` is reachable only from an
    ``OfferAccepted`` nobody publishes — see the note in ``src/main.py``.
    """
    account = Account.open("stu-1", "prog-csc")
    account.raise_charge(ChargeKind.SESSION, "sess-2026", Money(Decimal("100000.00")))
    account.apply_payment(
        gateway_ref="ref-1",
        amount=Money(Decimal(paid)),
        received_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    await repos.accounts().add(account)


class TestRegistering:
    async def test_a_cleared_student_is_registered(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_course(client, api)
        await _seed_offering(repos)
        await _seed_cleared_account(repos)

        response = await client.post(f"{api}/enrollment/registrations", json=REGISTRATION)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["outcome"] == "accepted"
        assert body["credit_units"] == 3, "the units came from the catalog, not from the request"
        assert body["is_carry_over"] is False
        assert body["seats_remaining"] == 29
        assert body["term"] == {
            "session_id": "sess-2026",
            "semester_id": "sem-1",
            "ordinal": 1,
            "label": "sess-2026 semester 1",
        }

    async def test_an_uncleared_student_is_refused_with_every_reason(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """A refusal is a 200. It answered the question; it did not fail to understand it."""
        await _seed_course(client, api)
        await _seed_offering(repos)

        response = await client.post(f"{api}/enrollment/registrations", json=REGISTRATION)
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "refused"
        assert [reason["reason"] for reason in body["reasons"]] == ["not financially cleared"]
        assert body["reasons"][0]["detail"], "a student is told what to do about it"

    async def test_a_part_paid_session_fee_below_seventy_percent_is_refused(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """The clearance rule, reached through Billing's read model and Enrollment's adapter."""
        await _seed_course(client, api)
        await _seed_offering(repos)
        await _seed_cleared_account(repos, paid="69999.99")

        response = await client.post(f"{api}/enrollment/registrations", json=REGISTRATION)
        assert response.json()["outcome"] == "refused"

    async def test_exactly_seventy_percent_clears_first_semester(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_course(client, api)
        await _seed_offering(repos)
        await _seed_cleared_account(repos, paid="70000.00")

        response = await client.post(f"{api}/enrollment/registrations", json=REGISTRATION)
        assert response.json()["outcome"] == "accepted"

    async def test_a_full_offering_refuses_with_capacity(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_course(client, api)
        await _seed_offering(repos, capacity=0)
        await _seed_cleared_account(repos)

        response = await client.post(f"{api}/enrollment/registrations", json=REGISTRATION)
        assert response.json()["outcome"] == "refused"
        assert "course at capacity" in [r["reason"] for r in response.json()["reasons"]]

    async def test_a_refusal_carries_all_its_reasons_not_the_first(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """A student who queues twice for information the university had both times."""
        await _seed_course(client, api)
        await _seed_offering(repos, capacity=0)

        reasons = {
            r["reason"]
            for r in (
                await client.post(f"{api}/enrollment/registrations", json=REGISTRATION)
            ).json()["reasons"]
        }
        assert reasons == {"course at capacity", "not financially cleared"}


class TestWhatTheCatalogSays:
    async def test_a_course_the_catalog_does_not_have_is_a_404(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """Proves the ``CourseInfoPort`` adapter is actually reading Course Catalog."""
        await _seed_offering(repos)
        response = await client.post(f"{api}/enrollment/registrations", json=REGISTRATION)
        assert response.status_code == 404
        assert response.json()["error"] == "CourseNotFoundError"

    async def test_a_course_not_run_this_term_is_a_404(self, client: AsyncClient, api: str) -> None:
        await _seed_course(client, api)
        response = await client.post(f"{api}/enrollment/registrations", json=REGISTRATION)
        assert response.status_code == 404
        assert response.json()["error"] == "CourseOfferingNotFoundError"

    async def test_a_retired_course_is_refused_rather_than_missing(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """Retirement crosses the port as a flag, not an absence: the two mean different things."""
        await _seed_course(client, api)
        await _seed_offering(repos)
        await _seed_cleared_account(repos)
        await client.post(f"{api}/course-catalog/courses/csc101/retirement")

        response = await client.post(f"{api}/enrollment/registrations", json=REGISTRATION)
        assert response.status_code == 200
        assert "course not active" in [r["reason"] for r in response.json()["reasons"]]


class TestTheRequestItself:
    async def test_an_ordinal_that_names_no_semester_is_refused_by_the_framework(
        self, client: AsyncClient, api: str
    ) -> None:
        response = await client.post(
            f"{api}/enrollment/registrations", json=REGISTRATION | {"semester_ordinal": 3}
        )
        assert response.status_code == 422
        assert response.json()["error"] == "RequestValidationError"

    async def test_the_credit_units_cannot_be_stated_by_the_caller(
        self, client: AsyncClient, api: str
    ) -> None:
        """A caller that could state them could state them wrongly, and the cap would follow."""
        response = await client.post(
            f"{api}/enrollment/registrations", json=REGISTRATION | {"credit_units": 1}
        )
        assert response.status_code == 422
