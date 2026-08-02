"""The ``SubmitGrade`` use case: load, decide, announce.

Orchestration only. The decision — may this lecturer grade this course, in this session,
for this semester — belongs to :class:`GradeSubmission` in the domain, and this module
does not restate any part of it.

Nothing is written. Grade submission produces a fact; Academic Records builds its record
from that fact (CLAUDE.md section 3), so this context has nothing to persist and no
transaction to open. The event is published only once every domain check has passed, so a
rejected submission leaves no trace anywhere.
"""

from dataclasses import dataclass

from faculty_department.application.errors import LecturerNotFoundError, SessionNotFoundError
from faculty_department.domain.events import GradeSubmitted
from faculty_department.domain.grade_submission import GradeSubmission
from faculty_department.ports.event_publisher import EventPublisherPort
from faculty_department.ports.lecturer_repository import LecturerRepositoryPort
from faculty_department.ports.session_repository import SessionRepositoryPort


@dataclass(frozen=True)
class SubmitGradeCommand:
    """What an inbound adapter must supply to submit one grade.

    Identifiers only: the use case loads the aggregates itself, so no caller can hand it
    a lecturer whose assignments it invented.
    """

    lecturer_id: str
    session_id: str
    student_id: str
    course_id: str
    semester_id: str
    score: int


class SubmitGrade:
    """A lecturer submits a grade for a student on a course they teach."""

    def __init__(
        self,
        lecturers: LecturerRepositoryPort,
        sessions: SessionRepositoryPort,
        events: EventPublisherPort,
    ) -> None:
        self._lecturers = lecturers
        self._sessions = sessions
        self._events = events

    def execute(self, command: SubmitGradeCommand) -> GradeSubmitted:
        """Publish and return the ``GradeSubmitted`` fact.

        Raises:
            LecturerNotFoundError: no such lecturer is stored.
            SessionNotFoundError: no such session is stored.
            FacultyDepartmentError: the submission is not permitted, or the score or an
                identifier is invalid. Domain errors pass through untranslated — the
                domain already says exactly what went wrong.
        """
        lecturer = self._lecturers.get(command.lecturer_id)
        if lecturer is None:
            raise LecturerNotFoundError(f"no lecturer stored with id {command.lecturer_id!r}")

        session = self._sessions.get(command.session_id)
        if session is None:
            raise SessionNotFoundError(f"no session stored with id {command.session_id!r}")

        event = GradeSubmission.submit(
            lecturer=lecturer,
            session=session,
            student_id=command.student_id,
            course_id=command.course_id,
            semester_id=command.semester_id,
            score=command.score,
        )

        self._events.publish(event)
        return event
