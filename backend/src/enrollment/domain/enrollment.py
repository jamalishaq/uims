"""The ``Enrollment`` aggregate: one student, one course, one term.

The unit of registration, and deliberately a small one. A student's whole load for a term
is several of these rather than one aggregate holding a list, because the things that
happen to a registration happen to it alone: this course is graded, that one is still
being taught, and a semester-wide aggregate would make every grade submission a write to
every course the student took.

The state machine is CLAUDE.md section 3's, and it is three states because the
university's year has three moments worth recording. ``REGISTERED`` is a student holding a
place while teaching goes on. ``AWAITING_GRADE`` is teaching over and the mark not in yet —
the state that lets a registry answer "what are we still waiting for?", which is the whole
reason it is distinct from the one before it. ``FINALIZED`` is the mark recorded and the
registration closed; it is terminal, and nothing moves out of it.

There is no drop or withdrawal, and its absence is a decision rather than an oversight.
Three states are what CLAUDE.md specifies; a fourth would need somebody to say when a drop
is still allowed, what it does to the seat, and whether a dropped course appears on a
transcript — none of which is inferable (CLAUDE.md section 6).

What is not here: whether this registration should have been allowed. Prerequisites,
credit-load caps, capacity and financial clearance are judged by ``EligibilityRule`` and
``CourseOffering`` *before* an ``Enrollment`` exists, because an aggregate that could
answer them would have to hold the student's entire history and the course's whole seat
count to do it. This aggregate records that a registration was made, and refuses to record
a transition that could not have happened.
"""

from enum import Enum

from enrollment.domain.errors import (
    EnrollmentAlreadyFinalizedError,
    EnrollmentNotAwaitingGradeError,
    EnrollmentNotRegisteredError,
    InvalidTermError,
)
from enrollment.domain.facts import CourseFacts
from enrollment.domain.values import Term, require_credit_units, require_identifier


class EnrollmentStatus(Enum):
    """Where a registration has got to. ``FINALIZED`` is terminal."""

    REGISTERED = "registered"
    AWAITING_GRADE = "awaiting grade"
    FINALIZED = "finalized"


class Enrollment:
    """A student's registration for one course in one term."""

    def __init__(
        self,
        enrollment_id: str,
        student_id: str,
        course_id: str,
        term: Term,
        credit_units: int,
        *,
        is_carry_over: bool = False,
    ) -> None:
        if not isinstance(term, Term):
            raise InvalidTermError("term must be a Term")
        self._enrollment_id = require_identifier(enrollment_id, "enrollment_id")
        self._student_id = require_identifier(student_id, "student_id")
        self._course_id = require_identifier(course_id, "course_id")
        self._term = term
        self._credit_units = require_credit_units(credit_units, "credit units")
        self._is_carry_over = bool(is_carry_over)
        self._status = EnrollmentStatus.REGISTERED

    @classmethod
    def register(
        cls,
        enrollment_id: str,
        student_id: str,
        course: CourseFacts,
        term: Term,
        *,
        is_carry_over: bool = False,
    ) -> "Enrollment":
        """Register a student for a course. The place is held and nothing is graded yet.

        Takes ``CourseFacts`` rather than a course id and a number so that the units and
        the course they belong to cannot be passed in disagreeing with each other.
        """
        return cls(
            enrollment_id=enrollment_id,
            student_id=student_id,
            course_id=course.course_id,
            term=term,
            credit_units=course.credit_units,
            is_carry_over=is_carry_over,
        )

    @classmethod
    def restore(
        cls,
        enrollment_id: str,
        student_id: str,
        course_id: str,
        term: Term,
        credit_units: int,
        *,
        is_carry_over: bool,
        status: EnrollmentStatus,
    ) -> "Enrollment":
        """Rebuild a registration from stored state. A persistence adapter is the only caller.

        Only ``status`` is unreachable otherwise, and it is unreachable for the reason the
        three states exist: ``await_grade`` refuses a registration already waiting on a mark
        and ``finalize`` refuses one already finalised, so replaying the machine on load would
        raise on any registration read twice. Everything else here is an ordinary constructor
        argument, which is why this takes a status and nothing else that ``__init__`` does not.

        Takes ``course_id`` and ``credit_units`` separately rather than the ``CourseFacts``
        :meth:`register` insists on. That insistence exists so a caller cannot pass units and
        a course that disagree; here they came off one row, written together, and asking a
        persistence adapter to rebuild a facts object it would immediately take apart would be
        ceremony rather than safety.
        """
        if not isinstance(status, EnrollmentStatus):
            raise InvalidTermError(f"stored status {status!r} is not an EnrollmentStatus")
        enrollment = cls(
            enrollment_id=enrollment_id,
            student_id=student_id,
            course_id=course_id,
            term=term,
            credit_units=credit_units,
            is_carry_over=is_carry_over,
        )
        enrollment._status = status
        return enrollment

    @property
    def enrollment_id(self) -> str:
        return self._enrollment_id

    @property
    def student_id(self) -> str:
        return self._student_id

    @property
    def course_id(self) -> str:
        return self._course_id

    @property
    def term(self) -> Term:
        return self._term

    @property
    def credit_units(self) -> int:
        """What the course was worth *when it was registered for*.

        Snapshotted rather than read back from the catalog. Course Catalog can amend a
        course's credit units, and a registration that re-read them would let last year's
        load change under a rule that has already been applied to it — a student who was
        within their cap in 2026 must stay within it in 2027.
        """
        return self._credit_units

    @property
    def is_carry_over(self) -> bool:
        """Whether this is a re-registration for a course previously attempted and failed.

        Recorded as a fact, judged by nothing here. Whether carry-overs are capped, take
        priority in a full offering, or must be cleared before new courses are taken are
        institutional policies nobody has stated (CLAUDE.md section 6); this flag is what
        those rules will read when somebody does.
        """
        return self._is_carry_over

    @property
    def status(self) -> EnrollmentStatus:
        return self._status

    @property
    def is_final(self) -> bool:
        """Whether the registration has reached the state it can never move out of."""
        return self._status is EnrollmentStatus.FINALIZED

    def await_grade(self) -> None:
        """Close teaching on this registration; the mark is now outstanding.

        Raises:
            EnrollmentAlreadyFinalizedError: the registration is finalised.
            EnrollmentNotRegisteredError: the mark is already outstanding.
        """
        self._reject_if_finalized()
        if self._status is not EnrollmentStatus.REGISTERED:
            raise EnrollmentNotRegisteredError(
                f"enrollment {self._enrollment_id} is {self._status.value} "
                "and is already waiting on a grade"
            )
        self._status = EnrollmentStatus.AWAITING_GRADE

    def finalize(self) -> None:
        """Close the registration: the grade is in and Academic Records holds it. Terminal.

        Deliberately says nothing about *what* the grade was. Grades belong to Academic
        Records, which builds its own model from ``GradeSubmitted`` and never queries this
        context (CLAUDE.md section 3); an ``Enrollment`` holding a grade would be a second
        copy of a record whose whole point is to be authoritative.

        Raises:
            EnrollmentAlreadyFinalizedError: the registration is already finalised.
            EnrollmentNotAwaitingGradeError: teaching has not been closed on it yet.
        """
        self._reject_if_finalized()
        if self._status is not EnrollmentStatus.AWAITING_GRADE:
            raise EnrollmentNotAwaitingGradeError(
                f"enrollment {self._enrollment_id} is {self._status.value} "
                "and is not waiting on a grade"
            )
        self._status = EnrollmentStatus.FINALIZED

    def _reject_if_finalized(self) -> None:
        if self.is_final:
            raise EnrollmentAlreadyFinalizedError(
                f"enrollment {self._enrollment_id} is finalized and cannot change"
            )

    def __repr__(self) -> str:
        return (
            f"Enrollment(enrollment_id={self._enrollment_id!r}, "
            f"student_id={self._student_id!r}, course_id={self._course_id!r}, "
            f"term={self._term!s}, status={self._status.name})"
        )
