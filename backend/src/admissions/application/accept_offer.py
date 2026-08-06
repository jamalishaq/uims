"""An applicant takes up the place they were offered.

The moment the rest of the system starts caring about them. Until now an applicant is
Admissions' private business; accepting is what opens a ledger in Billing, and it is the
first of the two facts this context publishes.

**Applicant-initiated, with no actor recorded.** ``Applicant``'s state machine describes
accepting and declining as the applicant's own response to an offer, and a registrar
accepting on somebody's behalf is a thing this system deliberately cannot express — the
counterpart, ``decline()``, is terminal, and an offer turned down by the wrong hand cannot
be given back.
"""

from dataclasses import dataclass

from admissions.application.errors import ApplicantNotFoundError
from admissions.domain.events import OfferAccepted
from admissions.ports.applicant_repository import ApplicantRepositoryPort
from admissions.ports.event_publisher import EventPublisherPort


@dataclass(frozen=True)
class AcceptOfferCommand:
    """An identifier only. What is being accepted is whatever the applicant was offered.

    Naming a program here would let a caller accept a place other than the one held, which
    is not a thing that happens — an offer is for one program and the answer is yes or no.
    """

    applicant_id: str


@dataclass(frozen=True)
class OfferTakenUp:
    """The applicant holds their place, and Billing has been told.

    ``program_id`` is the *offered* program, which is what every downstream context means by
    "their program" and what the ledger will be priced against.
    """

    applicant_id: str
    program_id: str
    session_id: str


class AcceptOffer:
    """Record an applicant's acceptance and announce it."""

    def __init__(
        self,
        applicants: ApplicantRepositoryPort,
        events: EventPublisherPort,
    ) -> None:
        self._applicants = applicants
        self._events = events

    async def execute(self, command: AcceptOfferCommand) -> OfferTakenUp:
        """Accept the outstanding offer, publish the fact, then store the applicant.

        **Published before saved, and the order is the point.** A crash between the two
        leaves a ledger opened for an applicant still stored as ``OFFERED`` — and retrying
        the acceptance heals it completely, because ``OpenAccountForOffer`` is idempotent and
        answers ``was_already_open``. Saving first would be the unrecoverable order:
        ``accept()`` refuses to run twice, so a publish that failed afterwards would strand
        an applicant who is accepted forever and has no ledger anybody can open.

        That is the same trade ``ConfirmPayment`` makes when it writes the ledger before the
        intent — do the half that a later attempt can absorb, and leave the half that cannot
        be repeated until last.

        Returns:
            OfferTakenUp: the applicant holds the place and Billing has been told.

        Raises:
            ApplicantNotFoundError: no application is stored under that id.
            NoOfferToRespondToError: the applicant holds no outstanding offer.
            OfferAlreadyRespondedToError: they have already accepted.
            ApplicationOutcomeFinalError: the application already reached an outcome.
        """
        applicant = await self._applicants.get(command.applicant_id)
        if applicant is None:
            raise ApplicantNotFoundError(f"no applicant stored with id {command.applicant_id!r}")

        applicant.accept()

        # Guaranteed present: ``accept()`` demands an outstanding offer, and an offer cannot
        # be outstanding without a program to hold it on — ``Applicant.restore`` refuses any
        # stored row that claims otherwise.
        program_id = applicant.offered_program_id
        await self._events.publish(
            OfferAccepted(
                applicant_id=applicant.applicant_id,
                program_id=program_id,
                session_id=applicant.session_id,
            )
        )
        await self._applicants.save(applicant)

        return OfferTakenUp(
            applicant_id=applicant.applicant_id,
            program_id=program_id,
            session_id=applicant.session_id,
        )
