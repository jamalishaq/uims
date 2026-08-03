"""The ``CourseOffering`` aggregate: one course, run once, and the seats in it.

Capacity is Enrollment's to own, and this is where it lives. Course Catalog holds a course
as a description with "no capacity, no register, no semester" — a course exists whether or
not anybody teaches it this year — and none of Enrollment's three query ports could supply
a seat count without one context acquiring the other's concerns. What is offered, to how
many, in which term, is a registration fact.

A capacity is not a number stored next to a count, it is an invariant, and the reason this
aggregate exists is to be the one place that invariant can be enforced. A use case that
read ``seats_taken``, compared it to ``capacity`` and wrote back would have a gap between
the read and the write, and two students registering at once would take the same last seat.
Asking the offering to claim the seat closes that gap: the check and the increment are one
operation on one aggregate. This is ``AdmissionCycle``'s argument about quotas, made again
about seats, because it is the same argument.

Full is answered, not raised. :meth:`claim_seat` returns ``CapacityExhausted`` (see
``outcomes.py``), which ``RegisterForCourse`` turns into a refusal alongside whatever else
was wrong with the registration.

What is not here: who may take a seat. Prerequisites, credit loads and financial clearance
are ``EligibilityRule``'s judgement, and this aggregate never sees a student. It counts
seats.
"""

from enrollment.domain.errors import (
    InvalidCapacityError,
    InvalidSeatsTakenError,
    InvalidTermError,
)
from enrollment.domain.outcomes import CapacityExhausted, SeatClaimed, SeatOutcome
from enrollment.domain.values import Term, require_identifier


def _require_count(value: int, field: str, error: type[Exception]) -> int:
    """Return ``value``, rejecting anything that is not a whole number of seats.

    ``True`` is an ``int`` to Python and a data-entry accident to a registry, so it is
    rejected explicitly.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise error(f"{field} must be a whole number")
    if value < 0:
        raise error(f"{field} cannot be negative, got {value}")
    return value


class CourseOffering:
    """One course as it is being run in one term, and the seats left in it."""

    def __init__(
        self,
        course_id: str,
        term: Term,
        capacity: int,
        *,
        seats_taken: int = 0,
    ) -> None:
        if not isinstance(term, Term):
            raise InvalidTermError("term must be a Term")
        self._course_id = require_identifier(course_id, "course_id")
        self._term = term
        self._capacity = _require_count(capacity, "capacity", InvalidCapacityError)
        self._seats_taken = _require_count(seats_taken, "seats_taken", InvalidSeatsTakenError)
        if self._seats_taken > self._capacity:
            raise InvalidSeatsTakenError(
                f"offering of course {self._course_id} in {self._term} cannot start with "
                f"{self._seats_taken} seats taken against a capacity of {self._capacity}"
            )

    @classmethod
    def open(cls, course_id: str, term: Term, capacity: int) -> "CourseOffering":
        """Open a course for registration this term. Every seat is still free.

        A capacity of zero is legal: a course listed but not run this term is an offering
        that is full from the moment it opens, which is a truthful thing to say about it
        and saves ``RegisterForCourse`` needing a second notion of "closed".
        """
        return cls(course_id, term, capacity)

    @property
    def course_id(self) -> str:
        return self._course_id

    @property
    def term(self) -> Term:
        return self._term

    @property
    def capacity(self) -> int:
        """How many students this offering can hold."""
        return self._capacity

    @property
    def seats_taken(self) -> int:
        """Seats claimed so far. Never exceeds :attr:`capacity`."""
        return self._seats_taken

    @property
    def seats_remaining(self) -> int:
        return self._capacity - self._seats_taken

    @property
    def is_full(self) -> bool:
        return self._seats_taken >= self._capacity

    def claim_seat(self) -> SeatOutcome:
        """Take a seat, if there is one.

        Returns:
            SeatClaimed: a seat was taken and the count went up by one.
            CapacityExhausted: the offering was already full. Nothing changed, and asking
                again will say the same thing — a full offering does not become fuller.
        """
        if self.is_full:
            return CapacityExhausted(
                course_id=self._course_id,
                term=self._term,
                capacity=self._capacity,
            )
        self._seats_taken += 1
        return SeatClaimed(
            course_id=self._course_id,
            term=self._term,
            seats_taken=self._seats_taken,
            capacity=self._capacity,
        )

    def __repr__(self) -> str:
        return (
            f"CourseOffering(course_id={self._course_id!r}, term={self._term!s}, "
            f"seats_taken={self._seats_taken}, capacity={self._capacity})"
        )
