"""What an aggregate answers when the answer is legitimately no.

These are *outcomes*, not events. Nothing publishes them, no port speaks them, and no
other context will ever see one: they are what :meth:`AdmissionCycle.offer` hands back to
the caller that asked. The shape is borrowed from a domain event — a frozen dataclass plus
a union alias — because the shape is a good one, not because these travel.

The distinction they exist to make is CLAUDE.md section 3's: quota-full is "a normal
domain outcome, not an error". A full cycle has not been asked to do something impossible;
it has been asked a question and has said no, and the caller — ``MakeOfferToApplicant`` —
goes on to try the applicant's alternative programs. Raising here would make the ordinary
path of the alternative-offer flow run on exceptions, and would let a caller that forgot
to catch quietly over-admit a program.

Each outcome carries the numbers the decision was made on rather than just a verdict. A
caller holding ``QuotaExhausted`` can say which cycle was full and how full without going
back to the aggregate, which matters because by the time it is read the aggregate may have
been asked again.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OfferRecorded:
    """A place was claimed. ``offers_made`` is the count *including* this one."""

    program_id: str
    session_id: str
    offers_made: int
    quota: int


@dataclass(frozen=True)
class QuotaExhausted:
    """The cycle had no place left. Nothing was claimed and nothing changed."""

    program_id: str
    session_id: str
    quota: int


OfferOutcome = OfferRecorded | QuotaExhausted
"""Everything :meth:`AdmissionCycle.offer` can answer. Callers must handle both."""
