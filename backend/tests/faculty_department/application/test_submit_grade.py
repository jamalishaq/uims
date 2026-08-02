"""The ``SubmitGrade`` use case, driven through its ports.

Two things are under test that the domain tests cannot see: that the use case loads the
real stored aggregates rather than trusting its caller, and that ``GradeSubmitted``
reaches the outside world through :class:`EventPublisherPort` — once, and only when the
domain permitted the submission.
"""

import pytest

from faculty_department.adapters.outbound import InMemoryEventPublisher
from faculty_department.application import (
    LecturerNotFoundError,
    SessionNotFoundError,
    SubmitGrade,
    SubmitGradeCommand,
)
from faculty_department.domain import (
    AcademicYear,
    GradeSubmitted,
    InvalidScoreError,
    Lecturer,
    LecturerNotAssignedToCourseError,
    MissingIdentifierError,
    Semester,
    SemesterNotInSessionError,
    SemesterOrdinal,
    Session,
    SessionNotOpenError,
)
from faculty_department.ports import LecturerRepositoryPort, SessionRepositoryPort

SESSION_ID = "sess-2026"
OTHER_SESSION_ID = "sess-2027"
FIRST_SEMESTER_ID = "sem-2026-1"
SECOND_SEMESTER_ID = "sem-2026-2"
LECTURER_ID = "lec-001"
DEPARTMENT_ID = "dept-csc"
COURSE_ID = "csc-101"
STUDENT_ID = "stu-2026-0001"


def a_planned_session(session_id: str = SESSION_ID) -> Session:
    return Session.plan(
        session_id,
        AcademicYear(2026),
        [
            Semester(FIRST_SEMESTER_ID, SemesterOrdinal.FIRST),
            Semester(SECOND_SEMESTER_ID, SemesterOrdinal.SECOND),
        ],
    )


def a_command(**overrides: object) -> SubmitGradeCommand:
    fields: dict[str, object] = {
        "lecturer_id": LECTURER_ID,
        "session_id": SESSION_ID,
        "student_id": STUDENT_ID,
        "course_id": COURSE_ID,
        "semester_id": FIRST_SEMESTER_ID,
        "score": 68,
    }
    fields.update(overrides)
    return SubmitGradeCommand(**fields)  # type: ignore[arg-type]


@pytest.fixture
def stored_lecturer(lecturers: LecturerRepositoryPort) -> Lecturer:
    """A lecturer assigned to CSC101 for the 2026/2027 session, already persisted."""
    lecturer = Lecturer(LECTURER_ID, DEPARTMENT_ID, "Dr Adaeze Okonkwo")
    lecturer.assign_to_course(COURSE_ID, SESSION_ID)
    lecturers.add(lecturer)
    return lecturer


@pytest.fixture
def open_session(sessions: SessionRepositoryPort) -> Session:
    """The 2026/2027 session, opened and persisted."""
    session = a_planned_session()
    session.open()
    sessions.add(session)
    return session


@pytest.mark.usefixtures("stored_lecturer", "open_session")
class TestSuccessfulSubmission:
    def test_the_grade_submitted_fact_is_returned(self, submit_grade: SubmitGrade) -> None:
        event = submit_grade.execute(a_command())

        assert event == GradeSubmitted(
            student_id=STUDENT_ID,
            course_id=COURSE_ID,
            semester_id=FIRST_SEMESTER_ID,
            grade=68,
        )

    def test_the_event_is_published_through_the_port(
        self, submit_grade: SubmitGrade, events: InMemoryEventPublisher
    ) -> None:
        event = submit_grade.execute(a_command())

        assert events.published == (event,)

    def test_each_submission_publishes_once_in_order(
        self, submit_grade: SubmitGrade, events: InMemoryEventPublisher
    ) -> None:
        first = submit_grade.execute(a_command(student_id="stu-2026-0001", score=41))
        second = submit_grade.execute(a_command(student_id="stu-2026-0002", score=73))

        assert events.published == (first, second)

    def test_either_semester_of_the_session_is_acceptable(self, submit_grade: SubmitGrade) -> None:
        event = submit_grade.execute(a_command(semester_id=SECOND_SEMESTER_ID))

        assert event.semester_id == SECOND_SEMESTER_ID

    def test_the_use_case_stores_nothing(
        self,
        submit_grade: SubmitGrade,
        lecturers: LecturerRepositoryPort,
        sessions: SessionRepositoryPort,
    ) -> None:
        """Academic Records builds the record from the event; this context has no write."""
        submit_grade.execute(a_command())

        assert lecturers.list_for_department(DEPARTMENT_ID) == (lecturers.get(LECTURER_ID),)
        assert len(sessions.list_all()) == 1
        assert sessions.list_all()[0].is_open


class TestUnknownAggregates:
    def test_an_unknown_lecturer_id_is_an_application_error(
        self, submit_grade: SubmitGrade, open_session: Session
    ) -> None:
        with pytest.raises(LecturerNotFoundError):
            submit_grade.execute(a_command(lecturer_id="lec-nobody"))

    def test_an_unknown_session_id_is_an_application_error(
        self, submit_grade: SubmitGrade, stored_lecturer: Lecturer
    ) -> None:
        with pytest.raises(SessionNotFoundError):
            submit_grade.execute(a_command(session_id="sess-nobody"))

    @pytest.mark.usefixtures("open_session")
    def test_nothing_is_published_when_the_lecturer_is_unknown(
        self, submit_grade: SubmitGrade, events: InMemoryEventPublisher
    ) -> None:
        with pytest.raises(LecturerNotFoundError):
            submit_grade.execute(a_command(lecturer_id="lec-nobody"))

        assert events.published == ()

    @pytest.mark.usefixtures("stored_lecturer")
    def test_nothing_is_published_when_the_session_is_unknown(
        self, submit_grade: SubmitGrade, events: InMemoryEventPublisher
    ) -> None:
        with pytest.raises(SessionNotFoundError):
            submit_grade.execute(a_command(session_id="sess-nobody"))

        assert events.published == ()


class TestDomainRejectionsReachTheCaller:
    """Domain errors pass through the use case untranslated, and publish nothing."""

    @pytest.mark.usefixtures("stored_lecturer")
    def test_a_lecturer_who_does_not_teach_the_course_cannot_grade_it(
        self, submit_grade: SubmitGrade, events: InMemoryEventPublisher, open_session: Session
    ) -> None:
        with pytest.raises(LecturerNotAssignedToCourseError):
            submit_grade.execute(a_command(course_id="csc-201"))

        assert events.published == ()

    def test_an_assignment_in_another_session_does_not_authorize_this_one(
        self,
        submit_grade: SubmitGrade,
        lecturers: LecturerRepositoryPort,
        events: InMemoryEventPublisher,
        open_session: Session,
    ) -> None:
        lecturer = Lecturer(LECTURER_ID, DEPARTMENT_ID, "Dr Chidi Nwosu")
        lecturer.assign_to_course(COURSE_ID, OTHER_SESSION_ID)
        lecturers.add(lecturer)

        with pytest.raises(LecturerNotAssignedToCourseError):
            submit_grade.execute(a_command())

        assert events.published == ()

    @pytest.mark.usefixtures("stored_lecturer")
    def test_a_planned_session_accepts_no_grades(
        self,
        submit_grade: SubmitGrade,
        sessions: SessionRepositoryPort,
        events: InMemoryEventPublisher,
    ) -> None:
        sessions.add(a_planned_session())

        with pytest.raises(SessionNotOpenError):
            submit_grade.execute(a_command())

        assert events.published == ()

    @pytest.mark.usefixtures("stored_lecturer")
    def test_a_closed_session_accepts_no_grades(
        self,
        submit_grade: SubmitGrade,
        sessions: SessionRepositoryPort,
        events: InMemoryEventPublisher,
        open_session: Session,
    ) -> None:
        open_session.close()
        sessions.save(open_session)

        with pytest.raises(SessionNotOpenError):
            submit_grade.execute(a_command())

        assert events.published == ()

    @pytest.mark.usefixtures("stored_lecturer", "open_session")
    def test_a_semester_from_another_session_is_rejected(
        self, submit_grade: SubmitGrade, events: InMemoryEventPublisher
    ) -> None:
        with pytest.raises(SemesterNotInSessionError):
            submit_grade.execute(a_command(semester_id="sem-2027-1"))

        assert events.published == ()

    @pytest.mark.usefixtures("stored_lecturer", "open_session")
    @pytest.mark.parametrize("score", [-1, 101, "68", 68.5, None])
    def test_an_invalid_score_is_rejected(
        self, submit_grade: SubmitGrade, events: InMemoryEventPublisher, score: object
    ) -> None:
        with pytest.raises(InvalidScoreError):
            submit_grade.execute(a_command(score=score))

        assert events.published == ()

    @pytest.mark.usefixtures("stored_lecturer", "open_session")
    @pytest.mark.parametrize("field", ["student_id", "course_id", "semester_id"])
    def test_a_blank_identifier_is_rejected(
        self, submit_grade: SubmitGrade, events: InMemoryEventPublisher, field: str
    ) -> None:
        with pytest.raises(MissingIdentifierError):
            submit_grade.execute(a_command(**{field: "   "}))

        assert events.published == ()
