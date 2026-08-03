"""Admissions over HTTP: the application form, and the two decisions that follow it.

``SubmitApplication`` checks the program through ``ProgramInfoPort``, which the composition
root wired to Faculty & Department's placement read. So these tests also pin the reconciliation
that adapter performs: a program is admitting *for a session* only when its own flag is set and
that session is open.
"""

from httpx import AsyncClient

from admissions.domain.entry_requirement import ProgramEntryRequirement
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
