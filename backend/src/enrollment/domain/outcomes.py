"""What an aggregate answers when the answer is legitimately no.

These are *outcomes*, not events. Nothing publishes them, no port speaks them, and no
other context will ever see one: they are what :meth:`CourseOffering.claim_seat` hands
back to the caller that asked. The shape — a frozen dataclass plus a union alias — is
borrowed from a domain event because the shape is a good one, not because these travel.

The distinction they exist to make is the one Admissions makes about quotas: a full course
has not been asked to do something impossible, it has been asked a question and has said
no. Raising here would put the ordinary end of every popular course's registration period
on the error path, and would let a caller that forgot to catch quietly overfill a lecture
theatre.

Each outcome carries the numbers the decision was made on rather than just a verdict, so a
caller holding a ``CapacityExhausted`` can say which offering was full and how full
without going back to the aggregate — which by then may have been asked again.
"""

from dataclasses import dataclass

from enrollment.domain.values import Term


@dataclass(frozen=True)
class SeatClaimed:
    """A seat was taken. ``seats_taken`` is the count *including* this one."""

    course_id: str
    term: Term
    seats_taken: int
    capacity: int


@dataclass(frozen=True)
class CapacityExhausted:
    """The offering had no seat left. Nothing was claimed and nothing changed."""

    course_id: str
    term: Term
    capacity: int


SeatOutcome = SeatClaimed | CapacityExhausted
"""Everything :meth:`CourseOffering.claim_seat` can answer. Callers must handle both."""
