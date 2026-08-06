"""The ``Lecturer`` aggregate: who a member of staff is, and what they teach.

Assignments are scoped to a session: teaching CSC101 in 2026/2027 says nothing
about who teaches it in 2027/2028. This is what stops a lecturer from being able
to grade a course forever on the strength of having taught it once.

**The profile fields are optional, and that is a statement about the data rather than a
default.** A lecturer whose rank nobody has entered yet is a real and common state, and
``None`` says exactly that. Giving ``rank`` a default would be inventing an institutional
fact — CLAUDE.md section 6's "a wrong guess becomes a load-bearing assumption" — and it would
be invisible, because a record defaulted to Lecturer II reads identically to one somebody
checked. This is ``BioData``'s argument in another context: "a record that cannot be created
without a phone number is a record that will be created with a fake one".

There is no promotion history. ``amend_profile`` replaces what is on file, which is what a
registrar editing a staff record does. When somebody was promoted, and by whom, is a
different aggregate that nobody has asked for.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from faculty_department.domain.errors import (
    DuplicateCourseAssignmentError,
    InvalidLecturerProfileError,
    LecturerNotAssignedToCourseError,
)
from faculty_department.domain.values import (
    EmploymentStatus,
    Qualification,
    Rank,
    require_identifier,
    require_text,
)


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

    def __init__(
        self,
        lecturer_id: str,
        department_id: str,
        full_name: str,
        *,
        rank: Rank | None = None,
        employment_status: EmploymentStatus | None = None,
        qualifications: Iterable[Qualification] = (),
    ) -> None:
        self._lecturer_id = require_identifier(lecturer_id, "lecturer_id")
        self._department_id = require_identifier(department_id, "department_id")
        self._full_name = require_text(full_name, "lecturer name")
        self._assignments: set[CourseAssignment] = set()
        self._rank = _validated_rank(rank)
        self._employment_status = _validated_status(employment_status)
        self._qualifications = _validated_qualifications(qualifications)

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
    def rank(self) -> Rank | None:
        """Where they sit on the ladder, or ``None`` if nobody has recorded it."""
        return self._rank

    @property
    def employment_status(self) -> EmploymentStatus | None:
        """The terms they are employed on, or ``None`` if nobody has recorded them."""
        return self._employment_status

    @property
    def qualifications(self) -> tuple[Qualification, ...]:
        """The degrees on file, in the order they were recorded. A tuple: callers cannot add."""
        return self._qualifications

    def amend_profile(
        self,
        *,
        rank: Rank | None = None,
        employment_status: EmploymentStatus | None = None,
        qualifications: Iterable[Qualification] = (),
    ) -> None:
        """Replace what is on file about this person.

        A wholesale replacement rather than three setters, because that is the shape of the
        act: a registrar opens a staff record, corrects it, and saves it. Omitting a field
        clears it, which is the same thing the form does, and is why the route behind this is
        a ``PUT``.

        Deliberately *not* a promotion. Nothing here records that a rank changed, when, or on
        whose authority — see the module docstring.
        """
        self._rank = _validated_rank(rank)
        self._employment_status = _validated_status(employment_status)
        self._qualifications = _validated_qualifications(qualifications)

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


def _validated_rank(rank: Rank | None) -> Rank | None:
    """``None`` means not recorded; anything that is not a :class:`Rank` is a caller's bug."""
    if rank is not None and not isinstance(rank, Rank):
        raise InvalidLecturerProfileError(f"rank must be a Rank, got {type(rank).__name__}")
    return rank


def _validated_status(status: EmploymentStatus | None) -> EmploymentStatus | None:
    if status is not None and not isinstance(status, EmploymentStatus):
        raise InvalidLecturerProfileError(
            f"employment_status must be an EmploymentStatus, got {type(status).__name__}"
        )
    return status


def _validated_qualifications(
    qualifications: Iterable[Qualification],
) -> tuple[Qualification, ...]:
    """A tuple of qualifications, rejecting duplicates.

    Order is kept because it is the order somebody entered them and means nothing else — but a
    degree listed twice is a data-entry slip rather than two degrees, and the same argument
    ``AlternativeProgramPolicy`` makes about repeats applies: the second one is unreachable as
    information, so it is somebody's finger slipping.
    """
    held = tuple(qualifications)
    for qualification in held:
        if not isinstance(qualification, Qualification):
            raise InvalidLecturerProfileError(
                f"qualifications must be Qualification values, got {type(qualification).__name__}"
            )
    if len(set(held)) != len(held):
        raise InvalidLecturerProfileError("a qualification is listed more than once")
    return held
