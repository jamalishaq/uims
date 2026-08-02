"""The ``Applicant`` aggregate: one person's passage from application to matriculation.

An application is not a form, it is a lifecycle. The same record is touched by a
screening officer, an admissions board, the applicant, a payment confirmation and finally
a registrar, and the rule that matters is which of those may act *when*. That rule lives
here, on the aggregate, rather than in the use cases that call it (CLAUDE.md section 4):
a use case that forgot to check would otherwise be able to matriculate someone who
declined their offer.

Two program ids, not one. ``applied_program_id`` is what the applicant asked for and
never changes — it is what they will say they applied for, whatever happens next.
``offered_program_id`` is what the university actually offered, which may be an
alternative program (CLAUDE.md section 3), and is what every downstream context means by
"their program". Collapsing them would lose the applicant's own account of events the
moment an alternative offer was made.

The fee-cleared flag is set by consuming ``AcceptanceFeePaid`` and gates
``Accepted → Matriculated``. Matriculation is deliberately *not* automatic on payment: it
is a human-triggered act that checks a flag someone else set. That separation is an
explicit design decision (CLAUDE.md section 4), which is why the flag and the transition
are two methods and not one.

What is not here: quotas, entry requirements, alternative-program policy, and the events
this aggregate's transitions will eventually announce. Deciding *whether* to offer is
``AdmissionCycle``'s and ``MakeOfferToApplicant``'s work; this aggregate only records
that the decision was made, and refuses to record one that could not have been.
"""

from enum import Enum

from admissions.domain.errors import (
    AcceptanceFeeNotClearedError,
    ApplicantAlreadyScreenedError,
    ApplicantNotScreenedError,
    ApplicationOutcomeFinalError,
    InvalidBioDataError,
    InvalidUtmeResultError,
    NoOfferToRespondToError,
    OfferAlreadyMadeError,
    OfferAlreadyRespondedToError,
    OfferNotAcceptedError,
)
from admissions.domain.values import BioData, UtmeResult, require_identifier


class ApplicationStatus(Enum):
    """Where an application has got to.

    ``APPLIED`` is where every application starts. ``DECLINED``, ``MATRICULATED`` and
    ``NO_OFFER_AVAILABLE`` are terminal: nothing moves out of them, including back.
    """

    APPLIED = "applied"
    SCREENED = "screened"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    MATRICULATED = "matriculated"
    NO_OFFER_AVAILABLE = "no offer available"


_FINAL_STATUSES = frozenset(
    {
        ApplicationStatus.DECLINED,
        ApplicationStatus.MATRICULATED,
        ApplicationStatus.NO_OFFER_AVAILABLE,
    }
)


class Applicant:
    """Someone who applied to the university for a given session."""

    def __init__(
        self,
        applicant_id: str,
        applied_program_id: str,
        session_id: str,
        bio_data: BioData,
        utme_result: UtmeResult,
    ) -> None:
        if not isinstance(bio_data, BioData):
            raise InvalidBioDataError("bio_data must be a BioData")
        if not isinstance(utme_result, UtmeResult):
            raise InvalidUtmeResultError("utme_result must be a UtmeResult")
        self._applicant_id = require_identifier(applicant_id, "applicant_id")
        self._applied_program_id = require_identifier(applied_program_id, "applied_program_id")
        self._session_id = require_identifier(session_id, "session_id")
        self._bio_data = bio_data
        self._utme_result = utme_result
        self._status = ApplicationStatus.APPLIED
        self._offered_program_id: str | None = None
        self._fee_cleared = False

    @classmethod
    def apply(
        cls,
        applicant_id: str,
        applied_program_id: str,
        session_id: str,
        bio_data: BioData,
        utme_result: UtmeResult,
    ) -> "Applicant":
        """Submit an application. Nothing has been decided yet: no offer, no fee, no place."""
        return cls(applicant_id, applied_program_id, session_id, bio_data, utme_result)

    @property
    def applicant_id(self) -> str:
        return self._applicant_id

    @property
    def applied_program_id(self) -> str:
        """The program applied for. Fixed for the life of the application."""
        return self._applied_program_id

    @property
    def offered_program_id(self) -> str | None:
        """The program actually offered, which may be an alternative. ``None`` until offered."""
        return self._offered_program_id

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def bio_data(self) -> BioData:
        return self._bio_data

    @property
    def utme_result(self) -> UtmeResult:
        return self._utme_result

    @property
    def status(self) -> ApplicationStatus:
        return self._status

    @property
    def is_fee_cleared(self) -> bool:
        """Whether the acceptance fee has been confirmed settled by Billing."""
        return self._fee_cleared

    @property
    def is_final(self) -> bool:
        """Whether the application has reached an outcome it can never move out of."""
        return self._status in _FINAL_STATUSES

    def screen(self) -> None:
        """Record that screening was performed.

        Screening *happened* is what this records, not screening *passed*. Whether the
        applicant's subjects qualify them is ``SubjectCombinationRule``'s judgement, and an
        applicant who fails it is not in an error state — they are screened and about to be
        told no offer is available.
        """
        self._reject_if_final()
        if self._status is not ApplicationStatus.APPLIED:
            raise ApplicantAlreadyScreenedError(
                f"applicant {self._applicant_id} was already screened"
            )
        self._status = ApplicationStatus.SCREENED

    def require_awaiting_decision(self) -> None:
        """Raise unless the applicant is screened and still waiting on an offer decision.

        The same guard :meth:`offer` and :meth:`record_no_offer` make, exposed so a caller
        can make it *before* doing something it cannot undo. ``MakeOfferToApplicant`` has to
        claim a place on an ``AdmissionCycle`` before it can offer that place to anybody,
        and the two aggregates are written in separate transactions (CLAUDE.md section 4) —
        so a place claimed for an applicant who turns out to be unscreened is a place with
        no rollback to give it back.

        Asking is not the same as being told. :meth:`offer` still makes the check itself,
        because an aggregate that trusted callers to have asked first would not be
        enforcing anything.
        """
        self._reject_if_screening_incomplete()

    def offer(self, program_id: str) -> None:
        """Offer the applicant a place on ``program_id``, which need not be the one applied for."""
        self._reject_if_screening_incomplete()
        self._offered_program_id = require_identifier(program_id, "program_id")
        self._status = ApplicationStatus.OFFERED

    def record_no_offer(self) -> None:
        """Close the application with no place to offer. Terminal, and not a failure state.

        Reached both by an applicant whose screening found them unqualified and by one for
        whom every cycle — applied program and alternatives alike — was full.
        """
        self._reject_if_screening_incomplete()
        self._status = ApplicationStatus.NO_OFFER_AVAILABLE

    def accept(self) -> None:
        """Take up the offer. What was offered is now the applicant's program, finally."""
        self._reject_if_no_offer_outstanding()
        self._status = ApplicationStatus.ACCEPTED

    def decline(self) -> None:
        """Turn the offer down. Terminal: an offer let go is not held open."""
        self._reject_if_no_offer_outstanding()
        self._status = ApplicationStatus.DECLINED

    def record_acceptance_fee_paid(self) -> None:
        """Record that the gating acceptance fee cleared, unlocking matriculation.

        Idempotent by design and deliberately checked first: ``AcceptanceFeePaid`` is
        delivered at least once, so a redelivery — including one that arrives after the
        registrar has already matriculated the applicant — must be a no-op rather than an
        error a handler has to catch and swallow.
        """
        if self._fee_cleared:
            return
        self._reject_if_final()
        if self._status is not ApplicationStatus.ACCEPTED:
            raise OfferNotAcceptedError(
                f"applicant {self._applicant_id} is {self._status.value} and owes no acceptance fee"
            )
        self._fee_cleared = True

    def matriculate(self) -> None:
        """Turn an accepted, fee-cleared applicant into a matriculated one. Terminal.

        Human-triggered, never automatic on payment (CLAUDE.md section 4). Only the
        acceptance fee gates this; an outstanding matriculation fee does not.
        """
        self._reject_if_final()
        if self._status is not ApplicationStatus.ACCEPTED:
            raise OfferNotAcceptedError(
                f"applicant {self._applicant_id} is {self._status.value} "
                "and has not accepted an offer"
            )
        if not self._fee_cleared:
            raise AcceptanceFeeNotClearedError(
                f"applicant {self._applicant_id} has not cleared the acceptance fee"
            )
        self._status = ApplicationStatus.MATRICULATED

    def _reject_if_final(self) -> None:
        if self.is_final:
            raise ApplicationOutcomeFinalError(
                f"applicant {self._applicant_id} is {self._status.value} and cannot change"
            )

    def _reject_if_screening_incomplete(self) -> None:
        """Guard shared by the two ways an application leaves screening: an offer, or none."""
        self._reject_if_final()
        if self._status is ApplicationStatus.APPLIED:
            raise ApplicantNotScreenedError(f"applicant {self._applicant_id} has not been screened")
        if self._status is not ApplicationStatus.SCREENED:
            raise OfferAlreadyMadeError(
                f"applicant {self._applicant_id} is {self._status.value} "
                "and has already been decided"
            )

    def _reject_if_no_offer_outstanding(self) -> None:
        """Guard shared by the two responses to an offer: accepting it, or declining it."""
        self._reject_if_final()
        if self._status is ApplicationStatus.ACCEPTED:
            raise OfferAlreadyRespondedToError(
                f"applicant {self._applicant_id} has already accepted their offer"
            )
        if self._status is not ApplicationStatus.OFFERED:
            raise NoOfferToRespondToError(
                f"applicant {self._applicant_id} is {self._status.value} and holds no offer"
            )

    def __repr__(self) -> str:
        return (
            f"Applicant(applicant_id={self._applicant_id!r}, "
            f"applied_program_id={self._applied_program_id!r}, "
            f"offered_program_id={self._offered_program_id!r}, status={self._status.name})"
        )
