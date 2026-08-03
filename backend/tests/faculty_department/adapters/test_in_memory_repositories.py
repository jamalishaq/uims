"""The contract every repository adapter must keep.

The add/save/get part is parametrized across all five repositories on purpose: these
adapters are the reference implementation of the ports, and the Postgres adapters of
Phase 6 have to behave identically. One repository quietly disagreeing about what
``save`` means is exactly the drift this catches.
"""

from collections.abc import Callable
from typing import Any

import pytest

from faculty_department.adapters.outbound import (
    InMemoryDepartmentRepository,
    InMemoryFacultyRepository,
    InMemoryLecturerRepository,
    InMemoryProgramRepository,
    InMemorySessionRepository,
)
from faculty_department.domain import (
    AcademicYear,
    Department,
    Faculty,
    Lecturer,
    Program,
    Semester,
    SemesterOrdinal,
    Session,
)
from faculty_department.ports import AggregateNotFoundError, DuplicateAggregateError

FACULTY_ID = "fac-sci"
DEPARTMENT_ID = "dept-csc"


def a_faculty(faculty_id: str = FACULTY_ID) -> Faculty:
    return Faculty(faculty_id, "Faculty of Science", "SCI")


def a_department(department_id: str = DEPARTMENT_ID, faculty_id: str = FACULTY_ID) -> Department:
    return Department(department_id, faculty_id, "Computer Science", "CSC")


def a_program(program_id: str = "prog-csc-bsc", department_id: str = DEPARTMENT_ID) -> Program:
    return Program.create(program_id, department_id, "B.Sc. Computer Science", "CSC-BSC")


def a_lecturer(lecturer_id: str = "lec-001", department_id: str = DEPARTMENT_ID) -> Lecturer:
    return Lecturer(lecturer_id, department_id, "Dr Adaeze Okonkwo")


def a_session(session_id: str = "sess-2026", start_year: int = 2026) -> Session:
    return Session.plan(
        session_id,
        AcademicYear(start_year),
        [
            Semester(f"{session_id}-1", SemesterOrdinal.FIRST),
            Semester(f"{session_id}-2", SemesterOrdinal.SECOND),
        ],
    )


# (repository factory, aggregate factory taking an id) for each of the five aggregates.
REPOSITORIES: list[tuple[str, Callable[[], Any], Callable[[str], Any]]] = [
    ("faculty", InMemoryFacultyRepository, a_faculty),
    ("department", InMemoryDepartmentRepository, a_department),
    ("program", InMemoryProgramRepository, a_program),
    ("lecturer", InMemoryLecturerRepository, a_lecturer),
    ("session", InMemorySessionRepository, a_session),
]


@pytest.fixture(params=REPOSITORIES, ids=[name for name, _, _ in REPOSITORIES])
def repository_and_factory(request: pytest.FixtureRequest) -> tuple[Any, Callable[[str], Any]]:
    _, make_repository, make_aggregate = request.param
    return make_repository(), make_aggregate


class TestSharedRepositoryContract:
    async def test_an_added_aggregate_comes_back(
        self, repository_and_factory: tuple[Any, Callable[[str], Any]]
    ) -> None:
        repository, make = repository_and_factory
        aggregate = make("id-001")

        await repository.add(aggregate)

        assert await repository.get("id-001") is aggregate

    async def test_an_unknown_id_returns_none(
        self, repository_and_factory: tuple[Any, Callable[[str], Any]]
    ) -> None:
        """Absence is an answer, not a failure."""
        repository, _ = repository_and_factory

        assert await repository.get("id-nobody") is None

    async def test_adding_a_second_aggregate_under_the_same_id_is_refused(
        self, repository_and_factory: tuple[Any, Callable[[str], Any]]
    ) -> None:
        repository, make = repository_and_factory
        first = make("id-001")
        await repository.add(first)

        with pytest.raises(DuplicateAggregateError):
            await repository.add(make("id-001"))

        assert await repository.get("id-001") is first

    async def test_save_replaces_a_stored_aggregate(
        self, repository_and_factory: tuple[Any, Callable[[str], Any]]
    ) -> None:
        repository, make = repository_and_factory
        await repository.add(make("id-001"))
        replacement = make("id-001")

        await repository.save(replacement)

        assert await repository.get("id-001") is replacement

    async def test_save_on_an_id_that_was_never_added_is_refused(
        self, repository_and_factory: tuple[Any, Callable[[str], Any]]
    ) -> None:
        repository, make = repository_and_factory

        with pytest.raises(AggregateNotFoundError):
            await repository.save(make("id-001"))

        assert await repository.get("id-001") is None

    async def test_aggregates_are_kept_apart(
        self, repository_and_factory: tuple[Any, Callable[[str], Any]]
    ) -> None:
        repository, make = repository_and_factory
        first, second = make("id-001"), make("id-002")

        await repository.add(first)
        await repository.add(second)

        assert await repository.get("id-001") is first
        assert await repository.get("id-002") is second


class TestListAll:
    async def test_faculties_are_listed_in_insertion_order(self) -> None:
        repository = InMemoryFacultyRepository()
        first, second = a_faculty("fac-sci"), a_faculty("fac-arts")
        await repository.add(first)
        await repository.add(second)

        assert await repository.list_all() == (first, second)

    async def test_sessions_are_listed_in_insertion_order(self) -> None:
        repository = InMemorySessionRepository()
        newer, older = a_session("sess-2027", 2027), a_session("sess-2026", 2026)
        await repository.add(newer)
        await repository.add(older)

        assert await repository.list_all() == (newer, older)

    async def test_an_empty_repository_lists_nothing(self) -> None:
        assert await InMemoryFacultyRepository().list_all() == ()


class TestFinders:
    async def test_departments_are_filtered_by_faculty(self) -> None:
        repository = InMemoryDepartmentRepository()
        computer_science = a_department("dept-csc", "fac-sci")
        physics = a_department("dept-phy", "fac-sci")
        await repository.add(computer_science)
        await repository.add(physics)
        await repository.add(a_department("dept-eng", "fac-arts"))

        assert await repository.list_for_faculty("fac-sci") == (computer_science, physics)

    async def test_programs_are_filtered_by_department(self) -> None:
        repository = InMemoryProgramRepository()
        computing = a_program("prog-csc-bsc", "dept-csc")
        await repository.add(computing)
        await repository.add(a_program("prog-phy-bsc", "dept-phy"))

        assert await repository.list_for_department("dept-csc") == (computing,)

    async def test_lecturers_are_filtered_by_department(self) -> None:
        repository = InMemoryLecturerRepository()
        okonkwo = a_lecturer("lec-001", "dept-csc")
        await repository.add(okonkwo)
        await repository.add(a_lecturer("lec-002", "dept-phy"))

        assert await repository.list_for_department("dept-csc") == (okonkwo,)

    async def test_a_department_with_no_members_lists_nothing(self) -> None:
        repository = InMemoryLecturerRepository()
        await repository.add(a_lecturer("lec-001", "dept-csc"))

        assert await repository.list_for_department("dept-nobody") == ()


class TestAssignmentsTravelWithTheLecturer:
    async def test_a_stored_lecturer_keeps_the_courses_they_were_assigned(self) -> None:
        """Assignments are part of the aggregate, so the repository must carry them."""
        repository = InMemoryLecturerRepository()
        lecturer = a_lecturer()
        lecturer.assign_to_course("csc-101", "sess-2026")
        await repository.add(lecturer)

        stored = await repository.get(lecturer.lecturer_id)

        assert stored is not None
        assert stored.is_assigned_to("csc-101", "sess-2026")
