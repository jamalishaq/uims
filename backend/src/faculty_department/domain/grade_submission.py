"""Grade submission: a lecturer acting on their own course.

This is a domain service rather than a method on either aggregate because the
decision reads two of them — the lecturer's assignments and the session's state.
It writes neither: it validates and produces an event, so no transaction spans
two aggregates.

The authorization question ("does this lecturer teach this course?") is answered
entirely from data this context already owns. It never leaves the context.
"""

from faculty_department.domain.errors import (
    LecturerNotAssignedToCourseError,
    SemesterNotInSessionError,
    SessionNotOpenError,
)
from faculty_department.domain.events import GradeSubmitted
from faculty_department.domain.lecturer import Lecturer
from faculty_department.domain.session import Session
from faculty_department.domain.values import Score, require_identifier


class GradeSubmission:
    """Validates a lecturer's grade submission and produces the resulting event."""

    @staticmethod
    def submit(
        *,
        lecturer: Lecturer,
        session: Session,
        student_id: str,
        course_id: str,
        semester_id: str,
        score: int,
    ) -> GradeSubmitted:
        """Return the ``GradeSubmitted`` fact, or raise if the submission is not permitted.

        Authorization is checked first: an unassigned lecturer is turned away
        before any other detail of the submission is considered.
        """
        student_id = require_identifier(student_id, "student_id")
        course_id = require_identifier(course_id, "course_id")
        semester_id = require_identifier(semester_id, "semester_id")

        if not lecturer.is_assigned_to(course_id, session.session_id):
            raise LecturerNotAssignedToCourseError(
                f"lecturer {lecturer.lecturer_id} is not assigned to course {course_id} "
                f"in session {session.session_id} and may not grade it"
            )

        if not session.is_open:
            raise SessionNotOpenError(
                f"session {session.session_id} is {session.status.value}; "
                "grades may only be submitted against an open session"
            )

        if not session.has_semester(semester_id):
            raise SemesterNotInSessionError(
                f"semester {semester_id} does not belong to session {session.session_id}"
            )

        return GradeSubmitted(
            student_id=student_id,
            course_id=course_id,
            semester_id=semester_id,
            grade=Score(score).value,
        )
