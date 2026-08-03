"""Outbound port for storing and retrieving enrollments."""

from abc import ABC, abstractmethod

from enrollment.domain.enrollment import Enrollment
from enrollment.domain.values import Term


class EnrollmentRepositoryPort(ABC):
    """Persistence for the ``Enrollment`` aggregate.

    There is no ``remove``. A registration is the university's record of what a student was
    taking and when, and Academic Records will hold a grade against a course this student
    registered for years after they graduate — a repository that could make a registration
    vanish would be a repository that could orphan a transcript line.
    """

    @abstractmethod
    def add(self, enrollment: Enrollment) -> None:
        """Store a new registration.

        Raises:
            DuplicateAggregateError: the enrollment id is already held.
        """

    @abstractmethod
    def save(self, enrollment: Enrollment) -> None:
        """Persist changes to a registration that is already stored.

        Raises:
            AggregateNotFoundError: the enrollment id was never added.
        """

    @abstractmethod
    def get(self, enrollment_id: str) -> Enrollment | None:
        """Return the registration, or ``None`` if no such id is held."""

    @abstractmethod
    def list_for_student_in_term(self, student_id: str, term: Term) -> tuple[Enrollment, ...]:
        """Every course this student is registered for this term, in the order registered.

        One query, two questions, and deliberately so: the credit load a new registration
        would add to is the sum of these, and whether the course is already registered is
        whether one of these names it. Two methods would be two round trips answering from
        two reads of the same rows, and a moment where the load and the duplicate check
        could disagree.

        Term-scoped rather than wholesale. A cap is measured over a term, and the whole of
        a student's registration history is not something this context reasons about in
        bulk — what little of the past it needs, it asks for by name below.
        """

    @abstractmethod
    def has_registered_before(self, student_id: str, course_id: str) -> bool:
        """Whether the student has ever registered for this course, in any term.

        Narrow on purpose. This answers exactly one question — is the registration in front
        of us a carry-over? — and a method that returned the history instead would invite
        callers to re-derive rules from it. Nothing about *when* or *how many times* enters
        any decision Enrollment makes today.
        """
