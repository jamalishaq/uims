"""What is actually in the rows, read back by somebody who did not write them.

Every other Postgres test in this suite reads through the repository that did the writing,
and that repository holds an identity map — so ``get`` hands back the instance it was given.
That is deliberate and it is what makes the existing application suites run unchanged
(``assert students.get("stu-0001") is student``), but it means those tests cannot tell a
correct mapping from a mapping that never ran.

So these read through a *second* repository over the same engine, with an empty map. Nothing
can come back except what the columns hold. A field the writer forgot, a status that did not
survive its enum, a child collection written to the wrong table: all of it surfaces here and
nowhere else.

Skipped unless the run is against Postgres, because there is nothing to round-trip otherwise.
"""

import pytest

from faculty_department.adapters.outbound.postgres import (
    PostgresDepartmentRepository,
    PostgresFacultyRepository,
    PostgresLecturerRepository,
    PostgresProgramRepository,
    PostgresSessionRepository,
)
from faculty_department.domain import (
    AcademicYear,
    Department,
    EmploymentStatus,
    Faculty,
    Lecturer,
    Program,
    Qualification,
    Rank,
    Semester,
    SemesterOrdinal,
    Session,
    SessionStatus,
)

pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def only_on_postgres(backend: str) -> None:
    if backend != "postgres":
        pytest.skip("there is nothing to round-trip through an in-memory dict")


def a_session(session_id: str = "sess-2026") -> Session:
    return Session.plan(
        session_id,
        AcademicYear(2026),
        [
            Semester(f"{session_id}-1", SemesterOrdinal.FIRST),
            Semester(f"{session_id}-2", SemesterOrdinal.SECOND),
        ],
    )


class TestEveryFieldSurvives:
    async def test_a_faculty_comes_back_whole(self, engine, clean_database) -> None:
        await PostgresFacultyRepository(engine).add(Faculty("fac-sci", "Faculty of Science", "SCI"))

        stored = await PostgresFacultyRepository(engine).get("fac-sci")

        assert stored is not None
        assert (stored.faculty_id, stored.name, stored.code) == (
            "fac-sci",
            "Faculty of Science",
            "SCI",
        )

    async def test_a_department_keeps_the_faculty_it_belongs_to(
        self, engine, clean_database
    ) -> None:
        await PostgresDepartmentRepository(engine).add(
            Department("dept-csc", "fac-sci", "Computer Science", "CSC")
        )

        stored = await PostgresDepartmentRepository(engine).get("dept-csc")

        assert stored is not None
        assert (stored.faculty_id, stored.name, stored.code) == (
            "fac-sci",
            "Computer Science",
            "CSC",
        )

    async def test_a_programs_admitting_flag_is_not_lost(self, engine, clean_database) -> None:
        """The field Admissions asks about through its own port. A default would be wrong."""
        program = Program.create("prog-csc-bsc", "dept-csc", "B.Sc. Computer Science", "CSC-BSC")
        program.open_admissions()
        await PostgresProgramRepository(engine).add(program)

        stored = await PostgresProgramRepository(engine).get("prog-csc-bsc")

        assert stored is not None
        assert stored.is_admitting is True

    async def test_a_closed_program_stays_closed(self, engine, clean_database) -> None:
        await PostgresProgramRepository(engine).add(
            Program.create("prog-mcb-bsc", "dept-mcb", "B.Sc. Microbiology", "MCB-BSC")
        )

        stored = await PostgresProgramRepository(engine).get("prog-mcb-bsc")

        assert stored is not None
        assert stored.is_admitting is False


class TestChildrenSurvive:
    async def test_a_lecturers_assignments_come_back_with_them(
        self, engine, clean_database
    ) -> None:
        """They are part of the aggregate, so a read that lost them would authorize nobody."""
        lecturer = Lecturer("lec-001", "dept-csc", "Dr Adaeze Okonkwo")
        lecturer.assign_to_course("csc-101", "sess-2026")
        lecturer.assign_to_course("csc-201", "sess-2026")
        await PostgresLecturerRepository(engine).add(lecturer)

        stored = await PostgresLecturerRepository(engine).get("lec-001")

        assert stored is not None
        assert stored.is_assigned_to("csc-101", "sess-2026")
        assert stored.is_assigned_to("csc-201", "sess-2026")
        assert len(stored.assignments) == 2

    async def test_a_lecturers_staff_record_comes_back_with_them(
        self, engine, clean_database
    ) -> None:
        """Rank and employment status are nullable columns and qualifications are a child
        table, so this is the read that proves an ordered list survives a round trip."""
        lecturer = Lecturer(
            "lec-002",
            "dept-csc",
            "Dr Bola Adeyemi",
            rank=Rank.SENIOR_LECTURER,
            employment_status=EmploymentStatus.FULL_TIME,
            qualifications=[
                Qualification("M.Sc", "Computer Science", "University of Lagos", 2009),
                Qualification("PhD", "Computer Science", "University of Ibadan", 2014),
            ],
        )
        await PostgresLecturerRepository(engine).add(lecturer)

        stored = await PostgresLecturerRepository(engine).get("lec-002")

        assert stored is not None
        assert stored.rank is Rank.SENIOR_LECTURER
        assert stored.employment_status is EmploymentStatus.FULL_TIME
        assert [held.degree for held in stored.qualifications] == ["M.Sc", "PhD"]

    async def test_an_unrecorded_staff_record_stays_unrecorded(
        self, engine, clean_database
    ) -> None:
        """``None`` must survive as ``None``. A round trip that invented a default would make
        "nobody has checked" indistinguishable from a rank somebody entered."""
        await PostgresLecturerRepository(engine).add(
            Lecturer("lec-003", "dept-csc", "Dr Chidi Nwosu")
        )

        stored = await PostgresLecturerRepository(engine).get("lec-003")

        assert stored is not None
        assert stored.rank is None
        assert stored.employment_status is None
        assert stored.qualifications == ()

    async def test_clearing_a_staff_record_removes_the_qualification_rows(
        self, engine, clean_database
    ) -> None:
        """Children are rewritten wholesale, so an amendment that drops them must remove rows."""
        repository = PostgresLecturerRepository(engine)
        lecturer = Lecturer(
            "lec-004",
            "dept-csc",
            "Dr Ada Eze",
            rank=Rank.PROFESSOR,
            qualifications=[Qualification("PhD", "Physics", "Ibadan", 2001)],
        )
        await repository.add(lecturer)

        lecturer.amend_profile()
        await repository.save(lecturer)

        stored = await PostgresLecturerRepository(engine).get("lec-004")
        assert stored is not None
        assert stored.rank is None
        assert stored.qualifications == ()

    async def test_withdrawing_an_assignment_is_persisted_as_an_absence(
        self, engine, clean_database
    ) -> None:
        """Children are rewritten wholesale, so a removal has to actually remove the row."""
        repository = PostgresLecturerRepository(engine)
        lecturer = Lecturer("lec-001", "dept-csc", "Dr Adaeze Okonkwo")
        lecturer.assign_to_course("csc-101", "sess-2026")
        lecturer.assign_to_course("csc-201", "sess-2026")
        await repository.add(lecturer)

        lecturer.withdraw_from_course("csc-101", "sess-2026")
        await repository.save(lecturer)

        stored = await PostgresLecturerRepository(engine).get("lec-001")
        assert stored is not None
        assert not stored.is_assigned_to("csc-101", "sess-2026")
        assert stored.is_assigned_to("csc-201", "sess-2026")

    async def test_a_sessions_semesters_come_back_in_ordinal_order(
        self, engine, clean_database
    ) -> None:
        await PostgresSessionRepository(engine).add(a_session())

        stored = await PostgresSessionRepository(engine).get("sess-2026")

        assert stored is not None
        assert [semester.ordinal for semester in stored.semesters] == [
            SemesterOrdinal.FIRST,
            SemesterOrdinal.SECOND,
        ]
        assert stored.has_semester("sess-2026-1")


class TestStatusSurvives:
    """``Session.restore`` exists for exactly this, and this is what proves it earns its keep."""

    async def test_an_open_session_is_still_open_when_read_back(
        self, engine, clean_database
    ) -> None:
        repository = PostgresSessionRepository(engine)
        session = a_session()
        session.open()
        await repository.add(session)

        stored = await PostgresSessionRepository(engine).get("sess-2026")

        assert stored is not None
        assert stored.status is SessionStatus.OPEN
        assert stored.is_open

    async def test_a_closed_session_is_still_closed_and_still_terminal(
        self, engine, clean_database
    ) -> None:
        repository = PostgresSessionRepository(engine)
        session = a_session()
        session.open()
        session.close()
        await repository.add(session)

        stored = await PostgresSessionRepository(engine).get("sess-2026")

        assert stored is not None
        assert stored.status is SessionStatus.CLOSED

    async def test_a_planned_session_is_not_quietly_opened_by_a_round_trip(
        self, engine, clean_database
    ) -> None:
        await PostgresSessionRepository(engine).add(a_session())

        stored = await PostgresSessionRepository(engine).get("sess-2026")

        assert stored is not None
        assert stored.status is SessionStatus.PLANNED

    async def test_opening_a_stored_session_is_persisted_by_save(
        self, engine, clean_database
    ) -> None:
        """The write half of the same claim: a transition has to reach the column."""
        repository = PostgresSessionRepository(engine)
        session = a_session()
        await repository.add(session)

        session.open()
        await repository.save(session)

        stored = await PostgresSessionRepository(engine).get("sess-2026")
        assert stored is not None
        assert stored.status is SessionStatus.OPEN


class TestOrderingSurvives:
    async def test_faculties_list_in_the_order_they_were_added(
        self, engine, clean_database
    ) -> None:
        """A table has no order; ``ordinal`` is what keeps the port's promise."""
        repository = PostgresFacultyRepository(engine)
        for index, code in enumerate(["SCI", "ART", "ENG", "LAW"]):
            await repository.add(Faculty(f"fac-{index}", f"Faculty of {code}", code))

        listed = await PostgresFacultyRepository(engine).list_all()

        assert [faculty.code for faculty in listed] == ["SCI", "ART", "ENG", "LAW"]

    async def test_updating_a_row_does_not_move_it_in_the_ordering(
        self, engine, clean_database
    ) -> None:
        """The failure a serial column exists to prevent: Postgres may move an updated row."""
        repository = PostgresFacultyRepository(engine)
        first = Faculty("fac-0", "Faculty of Science", "SCI")
        await repository.add(first)
        await repository.add(Faculty("fac-1", "Faculty of Arts", "ART"))

        first.rename("Faculty of Natural Sciences")
        await repository.save(first)

        listed = await PostgresFacultyRepository(engine).list_all()
        assert [faculty.faculty_id for faculty in listed] == ["fac-0", "fac-1"]
        assert listed[0].name == "Faculty of Natural Sciences"


class TestTheIdentityMapKeepsIdentity:
    """The half the existing suites depend on, asserted here rather than only by side effect.

    ``assert applicants.get(id) is applicant`` appears in three application tests that must
    not change, and it holds against a dict for free. Against a table it holds because the
    repository remembers what it stored.
    """

    async def test_one_repository_hands_back_the_object_it_was_given(
        self, engine, clean_database
    ) -> None:
        repository = PostgresFacultyRepository(engine)
        faculty = Faculty("fac-sci", "Faculty of Science", "SCI")
        await repository.add(faculty)

        assert await repository.get("fac-sci") is faculty

    async def test_a_change_that_was_never_saved_is_still_visible_to_its_own_repository(
        self, engine, clean_database
    ) -> None:
        """The in-memory store held live references and said so. This reproduces it.

        Not a licence to skip ``save`` — ``_store.py`` warns against leaning on this, and a
        second repository would not see the change. It is here so the swap does not silently
        change what a test that does lean on it means.
        """
        repository = PostgresFacultyRepository(engine)
        faculty = Faculty("fac-sci", "Faculty of Science", "SCI")
        await repository.add(faculty)

        faculty.rename("Faculty of Natural Sciences")

        held = await repository.get("fac-sci")
        assert held is not None
        assert held.name == "Faculty of Natural Sciences"

        elsewhere = await PostgresFacultyRepository(engine).get("fac-sci")
        assert elsewhere is not None
        assert elsewhere.name == "Faculty of Science"


class TestTheIdentityMapDoesNotHideAMissingRow:
    async def test_a_repository_that_never_wrote_finds_nothing(
        self, engine, clean_database
    ) -> None:
        """``get`` reads the row every time; the map decides which object, never whether."""
        assert await PostgresFacultyRepository(engine).get("fac-nobody") is None

    async def test_the_writing_repository_also_reads_the_row_rather_than_its_map(
        self, engine, clean_database
    ) -> None:
        """Truncating behind its back leaves the map warm and the table empty. Empty wins."""
        repository = PostgresFacultyRepository(engine)
        await repository.add(Faculty("fac-sci", "Faculty of Science", "SCI"))
        assert await repository.get("fac-sci") is not None

        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM faculty_department.faculties"))

        assert await repository.get("fac-sci") is None
