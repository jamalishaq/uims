"""The ``AdmissionCycle`` aggregate: one program's intake for one session.

A quota is not a number stored next to a count — it is an invariant, and the whole reason
this aggregate exists is to be the one place that invariant can be enforced. CLAUDE.md
section 5 names it as the example of an aggregate's transactional consistency boundary,
and section 4 forbids a transaction spanning two of them. A use case that read
``offers_made``, compared it to ``quota`` and wrote back would have a gap between the read
and the write, and two admissions officers working the same list would fill the last place
twice. Asking the cycle itself to claim the place closes that gap: the check and the
increment are one operation on one aggregate.

Quota-full is answered, not raised. :meth:`offer` returns ``QuotaExhausted`` (see
``outcomes.py``), because a program filling up is the expected end of every popular
program's cycle rather than a fault — it is precisely the moment
``MakeOfferToApplicant`` starts looking at alternative programs.

What is not here: who may be offered a place. Whether an applicant's UTME combination
qualifies them for this program is ``SubjectCombinationRule``'s judgement, and the cycle
never sees an applicant at all. It counts places. That separation is what lets the same
cycle be filled by a direct offer and by an alternative offer without knowing the
difference.
"""

from admissions.domain.errors import InvalidOffersMadeError, InvalidQuotaError
from admissions.domain.outcomes import OfferOutcome, OfferRecorded, QuotaExhausted
from admissions.domain.values import require_identifier


def _require_count(value: int, field: str, error: type[Exception]) -> int:
    """Return ``value``, rejecting anything that is not a whole number of places.

    ``True`` is an ``int`` to Python and a data-entry accident to an admissions office, so
    it is rejected explicitly — the same guard ``UtmeSubjectScore`` makes for scores.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise error(f"{field} must be a whole number")
    if value < 0:
        raise error(f"{field} cannot be negative, got {value}")
    return value


class AdmissionCycle:
    """The intake of one program for one session, and the places left in it."""

    def __init__(
        self,
        program_id: str,
        session_id: str,
        quota: int,
        *,
        offers_made: int = 0,
    ) -> None:
        self._program_id = require_identifier(program_id, "program_id")
        self._session_id = require_identifier(session_id, "session_id")
        self._quota = _require_count(quota, "quota", InvalidQuotaError)
        self._offers_made = _require_count(offers_made, "offers_made", InvalidOffersMadeError)
        if self._offers_made > self._quota:
            raise InvalidOffersMadeError(
                f"cycle for program {self._program_id} in session {self._session_id} cannot "
                f"start with {self._offers_made} offers against a quota of {self._quota}"
            )

    @classmethod
    def open(cls, program_id: str, session_id: str, quota: int) -> "AdmissionCycle":
        """Open a fresh cycle. Every place is still free.

        A quota of zero is legal: a program that is not admitting this session has a cycle
        that is full from the moment it opens, which is a truthful thing to say about it
        and keeps ``MakeOfferToApplicant`` from needing a second notion of "closed".
        """
        return cls(program_id, session_id, quota)

    @property
    def program_id(self) -> str:
        return self._program_id

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def quota(self) -> int:
        """How many places this program has to give this session."""
        return self._quota

    @property
    def offers_made(self) -> int:
        """Places claimed so far. Never exceeds :attr:`quota`."""
        return self._offers_made

    @property
    def places_remaining(self) -> int:
        return self._quota - self._offers_made

    @property
    def is_full(self) -> bool:
        return self._offers_made >= self._quota

    def offer(self) -> OfferOutcome:
        """Claim a place, if there is one.

        Returns:
            OfferRecorded: a place was claimed and the count went up by one.
            QuotaExhausted: the cycle was already full. Nothing changed, and asking again
                will say the same thing — a full cycle does not become fuller.
        """
        if self.is_full:
            return QuotaExhausted(
                program_id=self._program_id,
                session_id=self._session_id,
                quota=self._quota,
            )
        self._offers_made += 1
        return OfferRecorded(
            program_id=self._program_id,
            session_id=self._session_id,
            offers_made=self._offers_made,
            quota=self._quota,
        )

    def __repr__(self) -> str:
        return (
            f"AdmissionCycle(program_id={self._program_id!r}, "
            f"session_id={self._session_id!r}, "
            f"offers_made={self._offers_made}, quota={self._quota})"
        )
