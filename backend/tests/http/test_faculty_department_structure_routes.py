"""Building the university over HTTP: faculties, departments, programs, staff, calendar.

For five phases this context owned the most-queried data in the system and had no way to be
given any of it — every other suite seeded it by reaching into repositories, which is what
``test_faculty_department_routes.py`` still does for the two routes that predate this change.
Here the hierarchy is built through the API instead.

Two things are worth more than the CRUD. **Each level checks the one above it**, so a mistyped
id is a 404 at the moment somebody typed it rather than a dangling reference that resurfaces
as an applicant being told their program does not exist. And **opening a session bills a
cohort** — it is the only publisher of ``SessionOpened``, whose subscription has been wired
since Phase 4 with nothing to trigger it.
"""

from decimal import Decimal

from httpx import AsyncClient

from billing.domain import Account, FeeSchedule, Level, Money, SessionFeeLine

FACULTY = {"faculty_id": "fac-sci", "name": "Science", "code": "SCI"}
DEPARTMENT = {
    "department_id": "dept-csc",
    "faculty_id": "fac-sci",
    "name": "Computer Science",
    "code": "CSC",
}
PROGRAM = {
    "program_id": "prog-csc",
    "department_id": "dept-csc",
    "name": "BSc Computer Science",
    "code": "CSC",
}
PLANNED_SESSION = {
    "session_id": "sess-2026",
    "academic_year": 2026,
    "semesters": [
        {"semester_id": "sem-1", "ordinal": 1},
        {"semester_id": "sem-2", "ordinal": 2},
    ],
}


async def _build_hierarchy(client: AsyncClient, api: str) -> None:
    """Faculty, department and program, over HTTP and nothing else."""
    await client.post(f"{api}/faculty-department/faculties", json=FACULTY)
    await client.post(f"{api}/faculty-department/departments", json=DEPARTMENT)
    await client.post(f"{api}/faculty-department/programs", json=PROGRAM)


class TestCreatingTheStructure:
    async def test_the_whole_hierarchy_can_be_built_over_http(
        self, client: AsyncClient, api: str
    ) -> None:
        faculty = await client.post(f"{api}/faculty-department/faculties", json=FACULTY)
        department = await client.post(f"{api}/faculty-department/departments", json=DEPARTMENT)
        program = await client.post(f"{api}/faculty-department/programs", json=PROGRAM)

        assert faculty.status_code == 201, faculty.text
        assert department.status_code == 201, department.text
        assert program.status_code == 201, program.text
        assert program.json()["is_admitting"] is False, "a program is created closed"

    async def test_a_department_in_a_faculty_nobody_has_is_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        """A dangling reference would surface much later as a placement that cannot be read."""
        response = await client.post(
            f"{api}/faculty-department/departments",
            json=DEPARTMENT | {"faculty_id": "fac-nobody"},
        )
        assert response.status_code == 404
        assert response.json()["error"] == "FacultyNotFoundError"

    async def test_a_program_in_a_department_nobody_has_is_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        response = await client.post(
            f"{api}/faculty-department/programs", json=PROGRAM | {"department_id": "dept-nobody"}
        )
        assert response.status_code == 404
        assert response.json()["error"] == "DepartmentNotFoundError"

    async def test_a_repeated_faculty_id_is_a_409(self, client: AsyncClient, api: str) -> None:
        await client.post(f"{api}/faculty-department/faculties", json=FACULTY)

        response = await client.post(f"{api}/faculty-department/faculties", json=FACULTY)
        assert response.status_code == 409

    async def test_opening_admissions_is_a_separate_decision(
        self, client: AsyncClient, api: str
    ) -> None:
        await _build_hierarchy(client, api)

        response = await client.put(
            f"{api}/faculty-department/programs/prog-csc/admissions",
            json={"is_admitting": True},
        )

        assert response.status_code == 200, response.text
        assert response.json()["is_admitting"] is True

    async def test_setting_admissions_is_idempotent(self, client: AsyncClient, api: str) -> None:
        """PUT sets a state rather than requesting a transition."""
        await _build_hierarchy(client, api)
        url = f"{api}/faculty-department/programs/prog-csc/admissions"
        await client.put(url, json={"is_admitting": True})

        response = await client.put(url, json={"is_admitting": True})
        assert response.status_code == 200
        assert response.json()["is_admitting"] is True

    async def test_admissions_can_be_closed_again(self, client: AsyncClient, api: str) -> None:
        await _build_hierarchy(client, api)
        url = f"{api}/faculty-department/programs/prog-csc/admissions"
        await client.put(url, json={"is_admitting": True})

        response = await client.put(url, json={"is_admitting": False})
        assert response.json()["is_admitting"] is False

    async def test_a_program_nobody_has_cannot_have_admissions_set(
        self, client: AsyncClient, api: str
    ) -> None:
        response = await client.put(
            f"{api}/faculty-department/programs/prog-nobody/admissions",
            json={"is_admitting": True},
        )
        assert response.status_code == 404
        assert response.json()["error"] == "ProgramNotFoundError"


class TestListingADepartmentsPrograms:
    """The inverse of the placement read: how a client relates people to a department."""

    async def test_a_department_s_programs_come_back(self, client: AsyncClient, api: str) -> None:
        await _build_hierarchy(client, api)

        response = await client.get(f"{api}/faculty-department/departments/dept-csc/programs")

        assert response.status_code == 200, response.text
        assert [p["program_id"] for p in response.json()["programs"]] == ["prog-csc"]

    async def test_closed_programs_are_included(self, client: AsyncClient, api: str) -> None:
        """A program not admitting this session is a fact about it, not a reason to hide it."""
        await _build_hierarchy(client, api)

        response = await client.get(f"{api}/faculty-department/departments/dept-csc/programs")

        assert response.json()["programs"][0]["is_admitting"] is False

    async def test_a_department_nobody_has_lists_empty_rather_than_404(
        self, client: AsyncClient, api: str
    ) -> None:
        """The use case raises nothing, and an unknown department is indistinguishable from
        one that offers nothing yet."""
        response = await client.get(f"{api}/faculty-department/departments/dept-nobody/programs")
        assert response.status_code == 200
        assert response.json()["programs"] == []


class TestStaff:
    async def test_registering_a_lecturer_starts_them_teaching_nothing(
        self, client: AsyncClient, api: str
    ) -> None:
        """Who teaches what is decided again every session and moves separately."""
        await _build_hierarchy(client, api)

        response = await client.post(
            f"{api}/faculty-department/lecturers",
            json={
                "lecturer_id": "lec-1",
                "department_id": "dept-csc",
                "full_name": "Dr Adaeze Okonkwo",
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["assignments"] == []

    async def test_a_lecturer_in_a_department_nobody_has_is_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        response = await client.post(
            f"{api}/faculty-department/lecturers",
            json={
                "lecturer_id": "lec-1",
                "department_id": "dept-nobody",
                "full_name": "Dr Adaeze Okonkwo",
            },
        )
        assert response.status_code == 404
        assert response.json()["error"] == "DepartmentNotFoundError"


class TestTheCalendar:
    """Planning a session charges nobody. Opening one bills a cohort."""

    async def test_a_planned_session_is_not_open(self, client: AsyncClient, api: str) -> None:
        response = await client.post(f"{api}/faculty-department/sessions", json=PLANNED_SESSION)

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["is_open"] is False
        assert body["label"] == "2026/2027"
        assert [semester["ordinal"] for semester in body["semesters"]] == [1, 2]

    async def test_opening_a_session_charges_every_active_account(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """The subscription that had been wired for phases with nothing to trigger it.

        The ledger is seeded directly rather than through an accepted offer, because what is
        under test is the calendar reaching Billing — not the admissions chain, which
        ``tests/admissions/test_admissions_chain_wiring.py`` already walks end to end.
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
        await repos.accounts().add(
            Account.open(party_id="app-1", program_id="prog-csc", level=Level(100))
        )
        await client.post(f"{api}/faculty-department/sessions", json=PLANNED_SESSION)

        response = await client.post(f"{api}/faculty-department/sessions/sess-2026/opening")

        assert response.status_code == 200, response.text
        assert response.json()["is_open"] is True
        ledger = await client.get(f"{api}/billing/accounts/app-1")
        assert "session fee" in [charge["kind"] for charge in ledger.json()["charges"]]

    async def test_opening_a_session_twice_is_a_409(self, client: AsyncClient, api: str) -> None:
        await client.post(f"{api}/faculty-department/sessions", json=PLANNED_SESSION)
        await client.post(f"{api}/faculty-department/sessions/sess-2026/opening")

        response = await client.post(f"{api}/faculty-department/sessions/sess-2026/opening")
        assert response.status_code == 409

    async def test_opening_a_session_nobody_planned_is_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        response = await client.post(f"{api}/faculty-department/sessions/sess-nobody/opening")
        assert response.status_code == 404
        assert response.json()["error"] == "SessionNotFoundError"

    async def test_a_repeated_session_id_is_a_409(self, client: AsyncClient, api: str) -> None:
        await client.post(f"{api}/faculty-department/sessions", json=PLANNED_SESSION)

        response = await client.post(f"{api}/faculty-department/sessions", json=PLANNED_SESSION)
        assert response.status_code == 409
