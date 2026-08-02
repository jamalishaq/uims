"""Grade submission: a lecturer acting on their own course.

The rule under test is the one this context exists to enforce — authorization is
answered from data Faculty & Department already owns, never from another context.
"""

import pytest

from faculty_department.domain import (
    AcademicYear,
    GradeSubmission,
    GradeSubmitted,
    InvalidScoreError,
    Lecturer,
    LecturerNotAssignedToCourseError,
    MissingIdentifierError,
    Score,
    Semester,
    SemesterNotInSessionError,
    SemesterOrdinal,
    Session,
    SessionNotOpenError,
)

SESSION_ID = "sess-2026"
COURSE_ID = "csc-101"
STUDENT_ID = "stu-2026-0001"
FIRST_SEMESTER_ID = "sem-2026-1"


def a_planned_session() -> Session:
    return Session.plan(
        SESSION_ID,
        AcademicYear(2026),
        [
            Semester(FIRST_SEMESTER_ID, SemesterOrdinal.FIRST),
            Semester("sem-2026-2", SemesterOrdinal.SECOND),
        ],
    )


def an_open_session() -> Session:
    session = a_planned_session()
    session.open()
    return session


def the_assigned_lecturer() -> Lecturer:
    lecturer = Lecturer("lec-001", "dept-csc", "Dr Adaeze Okonkwo")
    lecturer.assign_to_course(COURSE_ID, SESSION_ID)
    return lecturer


def an_unassigned_lecturer() -> Lecturer:
    return Lecturer("lec-002", "dept-csc", "Dr Bola Adeyemi")


def submit(**overrides: object) -> GradeSubmitted:
    kwargs: dict[str, object] = {
        "lecturer": the_assigned_lecturer(),
        "session": an_open_session(),
        "student_id": STUDENT_ID,
        "course_id": COURSE_ID,
        "semester_id": FIRST_SEMESTER_ID,
        "score": 68,
    }
    kwargs.update(overrides)
    return GradeSubmission.submit(**kwargs)  # type: ignore[arg-type]


class TestValidSubmission:
    def test_an_assigned_lecturer_submits_a_grade(self) -> None:
        event = submit()

        assert event == GradeSubmitted(
            student_id=STUDENT_ID,
            course_id=COURSE_ID,
            semester_id=FIRST_SEMESTER_ID,
            grade=68,
        )

    def test_the_event_carries_the_raw_score_not_a_letter(self) -> None:
        """The score-to-letter scale belongs to Academic Records, not to this context."""
        assert submit(score=100).grade == 100
        assert isinstance(submit(score=0).grade, int)

    def test_either_semester_of_the_session_is_acceptable(self) -> None:
        assert submit(semester_id="sem-2026-2").semester_id == "sem-2026-2"

    def test_submission_does_not_change_the_lecturer_or_the_session(self) -> None:
        """The service reads two aggregates and writes neither."""
        lecturer = the_assigned_lecturer()
        session = an_open_session()

        GradeSubmission.submit(
            lecturer=lecturer,
            session=session,
            student_id=STUDENT_ID,
            course_id=COURSE_ID,
            semester_id=FIRST_SEMESTER_ID,
            score=68,
        )

        assert lecturer.assignments == the_assigned_lecturer().assignments
        assert session.is_open


class TestUnassignedLecturer:
    def test_a_lecturer_who_does_not_teach_the_course_cannot_grade_it(self) -> None:
        with pytest.raises(LecturerNotAssignedToCourseError):
            submit(lecturer=an_unassigned_lecturer())

    def test_a_lecturer_cannot_grade_a_course_they_teach_in_a_different_session(self) -> None:
        lecturer = Lecturer("lec-003", "dept-csc", "Dr Chidi Nwosu")
        lecturer.assign_to_course(COURSE_ID, "sess-2027")

        with pytest.raises(LecturerNotAssignedToCourseError):
            submit(lecturer=lecturer)

    def test_a_lecturer_cannot_grade_a_course_other_than_their_own(self) -> None:
        with pytest.raises(LecturerNotAssignedToCourseError):
            submit(course_id="csc-201")

    def test_a_withdrawn_lecturer_loses_the_authority_to_grade(self) -> None:
        lecturer = the_assigned_lecturer()
        lecturer.withdraw_from_course(COURSE_ID, SESSION_ID)

        with pytest.raises(LecturerNotAssignedToCourseError):
            submit(lecturer=lecturer)


class TestSessionState:
    def test_grades_cannot_be_submitted_against_a_planned_session(self) -> None:
        with pytest.raises(SessionNotOpenError):
            submit(session=a_planned_session())

    def test_grades_cannot_be_submitted_against_a_closed_session(self) -> None:
        session = an_open_session()
        session.close()

        with pytest.raises(SessionNotOpenError):
            submit(session=session)

    def test_a_semester_from_another_session_is_rejected(self) -> None:
        with pytest.raises(SemesterNotInSessionError):
            submit(semester_id="sem-2027-1")


class TestScore:
    @pytest.mark.parametrize("score", [-1, 101, 1000])
    def test_a_score_outside_zero_to_one_hundred_is_rejected(self, score: int) -> None:
        with pytest.raises(InvalidScoreError):
            submit(score=score)

    @pytest.mark.parametrize("score", ["68", 68.5, None, True])
    def test_a_score_that_is_not_a_whole_number_is_rejected(self, score: object) -> None:
        with pytest.raises(InvalidScoreError):
            submit(score=score)

    @pytest.mark.parametrize("score", [0, 1, 50, 99, 100])
    def test_the_whole_range_is_accepted(self, score: int) -> None:
        assert Score(score).value == score


class TestSubmissionIdentifiers:
    @pytest.mark.parametrize("field", ["student_id", "course_id", "semester_id"])
    def test_a_blank_identifier_is_rejected(self, field: str) -> None:
        with pytest.raises(MissingIdentifierError):
            submit(**{field: "   "})
