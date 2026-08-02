"""The ``Lecturer`` aggregate and the teaching assignments it holds.

Assignments are scoped to a session: teaching CSC101 in 2026/2027 says nothing
about who teaches it in 2027/2028. This is what stops a lecturer from being able
to grade a course forever on the strength of having taught it once.
"""

from dataclasses import dataclass

from faculty_department.domain.errors import (
    DuplicateCourseAssignmentError,
    LecturerNotAssignedToCourseError,
)
from faculty_department.domain.values import require_identifier, require_text


@dataclass(frozen=True)
class CourseAssignment:
    """A lecturer teaches this course for this session.

    ``course_id`` is Course Catalog's identifier, opaque to us.
    """

    course_id: str
    session_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "course_id", require_identifier(self.course_id, "course_id"))
        object.__setattr__(self, "session_id", require_identifier(self.session_id, "session_id"))


class Lecturer:
    """A member of academic staff and the courses they teach."""

    def __init__(self, lecturer_id: str, department_id: str, full_name: str) -> None:
        self._lecturer_id = require_identifier(lecturer_id, "lecturer_id")
        self._department_id = require_identifier(department_id, "department_id")
        self._full_name = require_text(full_name, "lecturer name")
        self._assignments: set[CourseAssignment] = set()

    @property
    def lecturer_id(self) -> str:
        return self._lecturer_id

    @property
    def department_id(self) -> str:
        return self._department_id

    @property
    def full_name(self) -> str:
        return self._full_name

    @property
    def assignments(self) -> frozenset[CourseAssignment]:
        """A copy: callers cannot reach in and grant themselves a course."""
        return frozenset(self._assignments)

    def assign_to_course(self, course_id: str, session_id: str) -> CourseAssignment:
        """Put this lecturer in charge of a course for one session."""
        assignment = CourseAssignment(course_id=course_id, session_id=session_id)
        if assignment in self._assignments:
            raise DuplicateCourseAssignmentError(
                f"lecturer {self._lecturer_id} already teaches course "
                f"{assignment.course_id} in session {assignment.session_id}"
            )
        self._assignments.add(assignment)
        return assignment

    def withdraw_from_course(self, course_id: str, session_id: str) -> None:
        assignment = CourseAssignment(course_id=course_id, session_id=session_id)
        if assignment not in self._assignments:
            raise LecturerNotAssignedToCourseError(
                f"lecturer {self._lecturer_id} does not teach course "
                f"{assignment.course_id} in session {assignment.session_id}"
            )
        self._assignments.discard(assignment)

    def is_assigned_to(self, course_id: str, session_id: str) -> bool:
        return CourseAssignment(course_id=course_id, session_id=session_id) in self._assignments

    def __repr__(self) -> str:
        return f"Lecturer(lecturer_id={self._lecturer_id!r}, assignments={len(self._assignments)})"
