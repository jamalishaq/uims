"""The academic calendar: session lifecycle and the semesters that subdivide a session."""

import pytest

from faculty_department.domain import (
    AcademicYear,
    FacultyDepartmentError,
    InvalidAcademicYearError,
    InvalidSemesterSetError,
    Semester,
    SemesterOrdinal,
    Session,
    SessionAlreadyClosedError,
    SessionAlreadyOpenError,
    SessionNotOpenError,
    SessionOpened,
    SessionStatus,
)

FIRST = Semester("sem-2026-1", SemesterOrdinal.FIRST)
SECOND = Semester("sem-2026-2", SemesterOrdinal.SECOND)


def a_session(session_id: str = "sess-2026") -> Session:
    return Session.plan(session_id, AcademicYear(2026), [FIRST, SECOND])


def an_open_session(session_id: str = "sess-2026") -> Session:
    session = a_session(session_id)
    session.open()
    return session


class TestAcademicYear:
    def test_renders_the_conventional_label(self) -> None:
        assert AcademicYear(2026).label == "2026/2027"

    def test_parses_the_conventional_label(self) -> None:
        assert AcademicYear.from_label("2026/2027") == AcademicYear(2026)

    @pytest.mark.parametrize("label", ["2026", "2026/2028", "2026-2027", "twenty/twentyone", ""])
    def test_rejects_labels_that_are_not_consecutive_years(self, label: str) -> None:
        with pytest.raises(FacultyDepartmentError):
            AcademicYear.from_label(label)

    @pytest.mark.parametrize("start_year", [0, 1899, 3000, -2026])
    def test_rejects_implausible_starting_years(self, start_year: int) -> None:
        with pytest.raises(InvalidAcademicYearError):
            AcademicYear(start_year)

    def test_years_order_chronologically(self) -> None:
        assert AcademicYear(2026) < AcademicYear(2027)


class TestSessionStructure:
    def test_a_planned_session_holds_both_semesters_in_ordinal_order(self) -> None:
        session = a_session()
        assert [semester.ordinal for semester in session.semesters] == [
            SemesterOrdinal.FIRST,
            SemesterOrdinal.SECOND,
        ]

    def test_semesters_are_built_in_ordinal_order_regardless_of_input_order(self) -> None:
        session = Session.plan("sess-2026", AcademicYear(2026), [SECOND, FIRST])
        assert session.semesters[0].ordinal is SemesterOrdinal.FIRST

    def test_knows_which_semesters_belong_to_it(self) -> None:
        session = a_session()
        assert session.has_semester("sem-2026-1")
        assert session.has_semester("sem-2026-2")
        assert not session.has_semester("sem-2027-1")

    @pytest.mark.parametrize(
        ("semesters", "reason"),
        [
            ([FIRST], "only one semester"),
            ([FIRST, SECOND, Semester("sem-2026-3", SemesterOrdinal.FIRST)], "three semesters"),
            ([FIRST, Semester("sem-2026-1b", SemesterOrdinal.FIRST)], "two firsts"),
            ([], "no semesters"),
        ],
    )
    def test_a_session_must_have_exactly_one_first_and_one_second_semester(
        self, semesters: list[Semester], reason: str
    ) -> None:
        with pytest.raises(InvalidSemesterSetError):
            Session.plan("sess-2026", AcademicYear(2026), semesters)

    def test_semester_ids_must_be_distinct(self) -> None:
        clash = Semester("sem-2026-1", SemesterOrdinal.SECOND)
        with pytest.raises(InvalidSemesterSetError):
            Session.plan("sess-2026", AcademicYear(2026), [FIRST, clash])

    def test_the_semester_collection_cannot_be_used_to_mutate_the_session(self) -> None:
        session = a_session()
        assert isinstance(session.semesters, tuple)
        with pytest.raises(TypeError):
            session.semesters[0] = SECOND  # type: ignore[index]


class TestSessionLifecycle:
    def test_a_new_session_is_planned_not_open(self) -> None:
        session = a_session()
        assert session.status is SessionStatus.PLANNED
        assert session.is_open is False

    def test_opening_announces_the_session(self) -> None:
        session = a_session()

        event = session.open()

        assert session.status is SessionStatus.OPEN
        assert session.is_open is True
        assert event == SessionOpened(session_id="sess-2026", academic_year=AcademicYear(2026))

    def test_closing_an_open_session_ends_it(self) -> None:
        session = an_open_session()

        session.close()

        assert session.status is SessionStatus.CLOSED
        assert session.is_open is False

    def test_a_planned_session_cannot_be_closed(self) -> None:
        session = a_session()
        with pytest.raises(SessionNotOpenError):
            session.close()
        assert session.status is SessionStatus.PLANNED

    def test_an_open_session_cannot_be_opened_again(self) -> None:
        session = an_open_session()
        with pytest.raises(SessionAlreadyOpenError):
            session.open()
        assert session.status is SessionStatus.OPEN

    def test_a_closed_session_cannot_be_reopened(self) -> None:
        session = an_open_session()
        session.close()
        with pytest.raises(SessionAlreadyClosedError):
            session.open()
        assert session.status is SessionStatus.CLOSED

    def test_a_closed_session_cannot_be_closed_twice(self) -> None:
        session = an_open_session()
        session.close()
        with pytest.raises(SessionAlreadyClosedError):
            session.close()
