"""Admissions over HTTP: the application form, and everything that follows it.

``SubmitApplication`` checks the program through ``ProgramInfoPort``, which the composition
root wired to Faculty & Department's placement read. So these tests also pin the reconciliation
that adapter performs: a program is admitting *for a session* only when its own flag is set and
that session is open.

The later classes go further than one context. Accepting an offer is the only thing that opens
a ledger, and matriculating is the only thing that creates a student, so the assertions reach
into Billing's routes and Student Profile's repository — which is the point: those crossings
are subscriptions made in ``src/main.py``, and a per-context test cannot see them at all.
"""

from decimal import Decimal

from httpx import AsyncClient

from admissions.domain.admission_cycle import AdmissionCycle
from admissions.domain.entry_requirement import ProgramEntryRequirement
from billing.domain import FeeSchedule, Level, Money, SessionFeeLine
from faculty_department.domain.department import Department
from faculty_department.domain.program import Program
from faculty_department.domain.session import Semester, SemesterOrdinal, Session
from faculty_department.domain.values import AcademicYear

APPLICATION = {
    "applicant_id": "app-1",
    "program_id": "prog-csc",
    "session_id": "sess-2026",
    "full_name": "Adaeze Okonkwo",
    "utme_scores": [
        {"subject": "ENGLISH", "score": 70},
        {"subject": "MATHEMATICS", "score": 80},
        {"subject": "PHYSICS", "score": 75},
        {"subject": "CHEMISTRY", "score": 65},
    ],
}


async def _seed_program(repos, *, admitting: bool = True, session_open: bool = True) -> None:
    await repos.departments().add(
        Department(
            department_id="dept-csc", faculty_id="fac-sci", name="Computer Science", code="CSC"
        )
    )
    program = Program.create(
        program_id="prog-csc", department_id="dept-csc", name="BSc Computer Science", code="CSC"
    )
    if admitting:
        program.open_admissions()
    await repos.programs().add(program)

    session = Session.plan(
        session_id="sess-2026",
        academic_year=AcademicYear(2026),
        semesters=[
            Semester("sem-1", SemesterOrdinal.FIRST),
            Semester("sem-2", SemesterOrdinal.SECOND),
        ],
    )
    if session_open:
        session.open()
    await repos.sessions().add(session)


async def _seed_requirement(
    repos, *, required: tuple[str, ...] = ("ENGLISH", "MATHEMATICS")
) -> None:
    await repos.requirements().add(
        ProgramEntryRequirement(
            program_id="prog-csc",
            session_id="sess-2026",
            required_subjects=required,
        )
    )


class TestSubmittingAnApplication:
    async def test_an_application_to_an_admitting_program_is_stored(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_program(repos)
        response = await client.post(f"{api}/admissions/applications", json=APPLICATION)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "applied"
        assert body["applied_program_id"] == "prog-csc"
        assert body["offered_program_id"] is None
        assert body["utme_aggregate"] == 290
        assert body["is_final"] is False

    async def test_a_program_faculty_and_department_does_not_have_is_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        """Proves ``ProgramInfoPort`` is reading the other context and not a stub."""
        response = await client.post(f"{api}/admissions/applications", json=APPLICATION)
        assert response.status_code == 404
        assert response.json()["error"] == "ProgramNotFoundError"

    async def test_a_program_not_admitting_is_a_422_not_a_404(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """A real program with a closed window is a form failing validation, not a missing thing."""
        await _seed_program(repos, admitting=False)
        response = await client.post(f"{api}/admissions/applications", json=APPLICATION)
        assert response.status_code == 422
        assert response.json()["error"] == "ProgramNotAdmittingError"

    async def test_a_closed_session_is_not_admitting_either(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """The reconciliation the adapter performs: the flag alone is not enough."""
        await _seed_program(repos, admitting=True, session_open=False)
        response = await client.post(f"{api}/admissions/applications", json=APPLICATION)
        assert response.status_code == 422
        assert response.json()["error"] == "ProgramNotAdmittingError"

    async def test_a_repeated_applicant_id_is_a_conflict(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_program(repos)
        await client.post(f"{api}/admissions/applications", json=APPLICATION)
        response = await client.post(f"{api}/admissions/applications", json=APPLICATION)
        assert response.status_code == 409

    async def test_three_subjects_is_not_a_utme_result(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """The count is the domain's rule, so the refusal comes from the domain, not the schema."""
        await _seed_program(repos)
        response = await client.post(
            f"{api}/admissions/applications",
            json=APPLICATION | {"utme_scores": APPLICATION["utme_scores"][:3]},
        )
        assert response.status_code == 422
        assert response.json()["error"] == "InvalidUtmeResultError"

    async def test_a_score_above_the_maximum_never_reaches_a_use_case(
        self, client: AsyncClient, api: str
    ) -> None:
        response = await client.post(
            f"{api}/admissions/applications",
            json=APPLICATION
            | {
                "utme_scores": [
                    {"subject": "ENGLISH", "score": 400},
                    *APPLICATION["utme_scores"][1:],
                ]
            },
        )
        assert response.status_code == 422
        assert response.json()["error"] == "RequestValidationError"


class TestScreening:
    async def test_a_qualified_applicant_is_reported_as_qualified(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_program(repos)
        await _seed_requirement(repos)
        await client.post(f"{api}/admissions/applications", json=APPLICATION)

        response = await client.post(f"{api}/admissions/applicants/app-1/screening")
        assert response.status_code == 200
        assert response.json() == {
            "outcome": "qualified",
            "applicant_id": "app-1",
            "program_id": "prog-csc",
        }

    async def test_failing_to_qualify_is_a_200_with_the_reasons(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """A decision about a candidate, not a bad request."""
        await _seed_program(repos)
        await _seed_requirement(repos, required=("BIOLOGY", "GEOGRAPHY"))
        await client.post(f"{api}/admissions/applications", json=APPLICATION)

        response = await client.post(f"{api}/admissions/applicants/app-1/screening")
        assert response.status_code == 200
        assert response.json()["outcome"] == "not_qualified"
        assert response.json()["unmet"], "the applicant is told what was missing"

    async def test_screening_twice_is_a_conflict(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_program(repos)
        await _seed_requirement(repos)
        await client.post(f"{api}/admissions/applications", json=APPLICATION)
        await client.post(f"{api}/admissions/applicants/app-1/screening")

        response = await client.post(f"{api}/admissions/applicants/app-1/screening")
        assert response.status_code == 409
        assert response.json()["error"] == "ApplicantAlreadyScreenedError"

    async def test_an_applicant_nobody_has_is_a_404(self, client: AsyncClient, api: str) -> None:
        response = await client.post(f"{api}/admissions/applicants/nobody/screening")
        assert response.status_code == 404


class TestOffers:
    async def test_an_unscreened_applicant_cannot_be_offered(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_program(repos)
        await client.post(f"{api}/admissions/applications", json=APPLICATION)

        response = await client.post(f"{api}/admissions/applicants/app-1/offer")
        assert response.status_code == 409
        assert response.json()["error"] == "ApplicantNotScreenedError"

    async def test_no_admission_cycle_for_the_applied_program_is_an_error(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """Only the *applied* program's missing cycle is an error; an alternative's is skipped."""
        await _seed_program(repos)
        await _seed_requirement(repos)
        await client.post(f"{api}/admissions/applications", json=APPLICATION)
        await client.post(f"{api}/admissions/applicants/app-1/screening")

        response = await client.post(f"{api}/admissions/applicants/app-1/offer")
        assert response.status_code == 404
        assert response.json()["error"] == "AdmissionCycleNotFoundError"


async def _seed_cycle(repos, quota: int = 2) -> None:
    await repos.cycles().add(AdmissionCycle.open("prog-csc", "sess-2026", quota))


async def _seed_fee_schedule(repos) -> None:
    """Billing has to be able to price the two admission charges, or accepting refuses.

    A session with no schedule at all refuses to open an account — "an account with no
    acceptance charge would gate matriculation on nothing" — so this is not optional dressing.
    """
    await repos.schedules().add(
        FeeSchedule.for_session(
            "sess-2026",
            acceptance_fee=Money(Decimal("20000")),
            matriculation_fee=Money(Decimal("50000")),
            session_fees=(
                SessionFeeLine(
                    program_id="prog-csc", level=Level(100), amount=Money(Decimal("100000"))
                ),
            ),
        )
    )


async def _offer_held(client: AsyncClient, api: str, repos) -> None:
    """Drive an applicant all the way to holding an offer, over HTTP only."""
    await _seed_program(repos)
    await _seed_requirement(repos)
    await _seed_cycle(repos)
    await _seed_fee_schedule(repos)
    await client.post(f"{api}/admissions/applications", json=APPLICATION)
    await client.post(f"{api}/admissions/applicants/app-1/screening")
    await client.post(f"{api}/admissions/applicants/app-1/offer")


class TestAnsweringAnOffer:
    async def test_accepting_opens_the_ledger(self, client: AsyncClient, api: str, repos) -> None:
        """The composition root's subscription, proven end to end over the wire."""
        await _offer_held(client, api, repos)

        response = await client.post(f"{api}/admissions/applicants/app-1/acceptance")

        assert response.status_code == 201, response.text
        assert response.json()["program_id"] == "prog-csc"

        ledger = await client.get(f"{api}/billing/accounts/app-1")
        assert ledger.status_code == 200
        assert [charge["kind"] for charge in ledger.json()["charges"]] == [
            "acceptance fee",
            "matriculation fee",
        ]

    async def test_accepting_twice_is_a_409(self, client: AsyncClient, api: str, repos) -> None:
        await _offer_held(client, api, repos)
        await client.post(f"{api}/admissions/applicants/app-1/acceptance")

        response = await client.post(f"{api}/admissions/applicants/app-1/acceptance")
        assert response.status_code == 409
        assert response.json()["error"] == "OfferAlreadyRespondedToError"

    async def test_an_applicant_holding_no_offer_cannot_accept(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_program(repos)
        await client.post(f"{api}/admissions/applications", json=APPLICATION)

        response = await client.post(f"{api}/admissions/applicants/app-1/acceptance")
        assert response.status_code == 409
        assert response.json()["error"] == "NoOfferToRespondToError"

    async def test_declining_returns_the_place_to_the_quota(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _offer_held(client, api, repos)

        response = await client.post(f"{api}/admissions/applicants/app-1/declination")

        assert response.status_code == 200, response.text
        assert response.json()["places_remaining"] == 2
        cycle = await repos.cycles().get("prog-csc", "sess-2026")
        assert cycle is not None and cycle.offers_made == 0

    async def test_declining_opens_no_ledger(self, client: AsyncClient, api: str, repos) -> None:
        await _offer_held(client, api, repos)
        await client.post(f"{api}/admissions/applicants/app-1/declination")

        assert (await client.get(f"{api}/billing/accounts/app-1")).status_code == 404

    async def test_an_applicant_nobody_has_is_a_404(self, client: AsyncClient, api: str) -> None:
        response = await client.post(f"{api}/admissions/applicants/nobody/acceptance")
        assert response.status_code == 404


class TestMatriculation:
    async def test_the_whole_chain_produces_a_student(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """Apply, screen, offer, accept, pay, matriculate — and a matric number exists."""
        await _offer_held(client, api, repos)
        await client.post(f"{api}/admissions/applicants/app-1/acceptance")
        await client.post(
            f"{api}/billing/accounts/app-1/payments",
            json={
                "gateway_ref": "psk-ref-1",
                "amount": "20000",
                "received_at": "2026-08-01T12:00:00Z",
            },
        )

        response = await client.post(f"{api}/admissions/applicants/app-1/matriculation")

        assert response.status_code == 201, response.text
        student = await repos.students().find_by_applicant("app-1")
        assert student is not None
        assert str(student.matric_number).startswith("260591")

    async def test_matriculation_before_the_fee_clears_is_a_409(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _offer_held(client, api, repos)
        await client.post(f"{api}/admissions/applicants/app-1/acceptance")

        response = await client.post(f"{api}/admissions/applicants/app-1/matriculation")
        assert response.status_code == 409
        assert response.json()["error"] == "AcceptanceFeeNotClearedError"

    async def test_an_applicant_who_never_accepted_cannot_matriculate(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _offer_held(client, api, repos)

        response = await client.post(f"{api}/admissions/applicants/app-1/matriculation")
        assert response.status_code == 409
        assert response.json()["error"] == "OfferNotAcceptedError"
