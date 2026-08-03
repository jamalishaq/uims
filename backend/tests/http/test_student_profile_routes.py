"""Student Profile over HTTP: the manual registration path, and the matric number it issues.

The matric number is the interesting part. It is composed from a department code and an entry
year that Faculty & Department supplies, through ``DepartmentCodePort``, whose live adapter
translates that context's alphabetic ``CSC`` into the four digits a matric number carries —
using a register the composition root reads from configuration and that has no default.

So these tests pin two things at once: the format (``260591001``), and the refusal when the
register has no entry for a department, which is the failure that must be loud.
"""

from httpx import AsyncClient

from faculty_department.domain.department import Department
from faculty_department.domain.program import Program
from faculty_department.domain.session import Semester, SemesterOrdinal, Session
from faculty_department.domain.values import AcademicYear

REGISTRATION = {
    "student_id": "stu-1",
    "program_id": "prog-csc",
    "entry_session_id": "sess-2026",
    "full_name": "Chinedu Eze",
}


async def _seed_program(repos, *, department_code: str = "CSC") -> None:
    await repos.departments().add(
        Department(
            department_id="dept-csc",
            faculty_id="fac-sci",
            name="Computer Science",
            code=department_code,
        )
    )
    await repos.programs().add(
        Program.create(
            program_id="prog-csc",
            department_id="dept-csc",
            name="BSc Computer Science",
            code="CSC",
        )
    )
    session = Session.plan(
        session_id="sess-2026",
        academic_year=AcademicYear(2026),
        semesters=[
            Semester("sem-1", SemesterOrdinal.FIRST),
            Semester("sem-2", SemesterOrdinal.SECOND),
        ],
    )
    session.open()
    await repos.sessions().add(session)


class TestRegisteringAStudent:
    async def test_a_student_is_created_with_a_matric_number(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_program(repos)
        response = await client.post(f"{api}/student-profile/students", json=REGISTRATION)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["matric_number"] == "260591001", (
            "two digits of entry year, four of numeric department code, then the intake sequence"
        )
        assert body["entry_level"] == 100
        assert body["applicant_id"] is None

    async def test_the_caller_cannot_supply_a_matric_number(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """A request that could name one could collide with a number a living student holds."""
        await _seed_program(repos)
        response = await client.post(
            f"{api}/student-profile/students", json=REGISTRATION | {"matric_number": "260591999"}
        )
        assert response.status_code == 422
        assert response.json()["error"] == "RequestValidationError"

    async def test_two_students_in_one_department_and_year_get_sequential_numbers(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_program(repos)
        first = await client.post(f"{api}/student-profile/students", json=REGISTRATION)
        second = await client.post(
            f"{api}/student-profile/students",
            json=REGISTRATION | {"student_id": "stu-2", "full_name": "Ngozi Bello"},
        )
        assert first.json()["matric_number"] == "260591001"
        assert second.json()["matric_number"] == "260591002"

    async def test_a_department_with_no_numeric_code_registered_refuses(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """The register is configuration with no default, and a gap in it must not be guessed.

        Issuing against an unconfirmed code would mint a permanent identifier around a guess,
        and a matric number is not something a registrar can quietly take back.
        """
        await _seed_program(repos, department_code="MTH")
        response = await client.post(f"{api}/student-profile/students", json=REGISTRATION)
        assert response.status_code == 422
        assert response.json()["error"] == "ProgramPlacementUnknownError"

    async def test_a_program_faculty_and_department_does_not_have_refuses(
        self, client: AsyncClient, api: str
    ) -> None:
        response = await client.post(f"{api}/student-profile/students", json=REGISTRATION)
        assert response.status_code == 422
        assert response.json()["error"] == "ProgramPlacementUnknownError"

    async def test_a_repeated_student_id_is_a_conflict(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_program(repos)
        await client.post(f"{api}/student-profile/students", json=REGISTRATION)
        response = await client.post(f"{api}/student-profile/students", json=REGISTRATION)
        assert response.status_code == 409

    async def test_an_applicant_id_links_the_two_records_when_supplied(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """Optional because this is the manual path: a student who never applied has none."""
        await _seed_program(repos)
        response = await client.post(
            f"{api}/student-profile/students", json=REGISTRATION | {"applicant_id": "app-1"}
        )
        assert response.json()["applicant_id"] == "app-1"
