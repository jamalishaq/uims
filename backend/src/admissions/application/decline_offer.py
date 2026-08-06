"""An applicant turns down the place they were offered, and the place goes back.

Two aggregates, so no transaction spans them (CLAUDE.md section 4) and the order is chosen
by which failure the university can live with — see :meth:`DeclineOffer.execute`.

**Nothing is published.** No other context was ever told the offer existed, so none of them
needs telling it is over: Billing opens a ledger at *acceptance*, and a declined applicant
never had one. The place freed goes back to the cycle this use case is already holding.
"""

from dataclasses import dataclass

from admissions.application.errors import AdmissionCycleNotFoundError, ApplicantNotFoundError
from admissions.ports.admission_cycle_repository import AdmissionCycleRepositoryPort
from admissions.ports.applicant_repository import ApplicantRepositoryPort


@dataclass(frozen=True)
class DeclineOfferCommand:
    """An identifier only, for ``AcceptOfferCommand``'s reason: there is one offer to answer."""

    applicant_id: str


@dataclass(frozen=True)
class OfferDeclined:
    """The applicant let their place go, and the cycle has it back.

    ``places_remaining`` is reported because it is the number the decline actually changed,
    and a registrar watching a program fill up is watching this figure.
    """

    applicant_id: str
    program_id: str
    session_id: str
    places_remaining: int


class DeclineOffer:
    """Record an applicant's refusal and return their place to the quota."""

    def __init__(
        self,
        applicants: ApplicantRepositoryPort,
        cycles: AdmissionCycleRepositoryPort,
    ) -> None:
        self._applicants = applicants
        self._cycles = cycles

    async def execute(self, command: DeclineOfferCommand) -> OfferDeclined:
        """Decline the offer, store it, then give the place back.

        **The applicant is saved first, and the ordering is the opposite of ``AcceptOffer``'s
        for a reason.** There is no idempotent listener to heal a half-finished decline, so
        the question is only which half-finished state is survivable:

        * *Applicant first* — a crash before the release leaves the applicant ``DECLINED``
          with their place still counted. The program under-admits by one, which an
          administrator can see and correct.
        * *Release first* — a crash leaves a free place while the applicant is still stored
          as ``OFFERED``. That place gets offered to somebody else, the original applicant
          can still accept, and the program over-admits. By the time anyone notices, both
          have matric numbers.

        Under-admit over over-admit, which is exactly what ``MakeOfferToApplicant._claim``
        decided in the other direction when it claimed the place before recording who held
        it.

        Saving first also makes double-release impossible without a guard: ``decline()``
        refuses a second call because ``DECLINED`` is terminal, so a repeat raises before the
        cycle is ever loaded.

        Returns:
            OfferDeclined: the offer is refused and the place is back on the cycle.

        Raises:
            ApplicantNotFoundError: no application is stored under that id.
            AdmissionCycleNotFoundError: the applicant declined, but the cycle their place
                was claimed on is gone. The refusal stands and the place is not returned.
            NoOfferToRespondToError: the applicant holds no outstanding offer.
            OfferAlreadyRespondedToError: they have already accepted.
            ApplicationOutcomeFinalError: the application already reached an outcome.
        """
        applicant = await self._applicants.get(command.applicant_id)
        if applicant is None:
            raise ApplicantNotFoundError(f"no applicant stored with id {command.applicant_id!r}")

        applicant.decline()
        # Present for ``AcceptOffer``'s reason: a declined application is one an offer was
        # made on, and ``Applicant.restore`` rejects any stored row that says otherwise.
        program_id = applicant.offered_program_id
        await self._applicants.save(applicant)

        cycle = await self._cycles.get(program_id, applicant.session_id)
        if cycle is None:
            raise AdmissionCycleNotFoundError(
                f"applicant {command.applicant_id!r} declined a place on program "
                f"{program_id!r}, but no admission cycle is stored for it in session "
                f"{applicant.session_id!r}; the place was not returned to the quota"
            )
        cycle.release()
        await self._cycles.save(cycle)

        return OfferDeclined(
            applicant_id=applicant.applicant_id,
            program_id=program_id,
            session_id=applicant.session_id,
            places_remaining=cycle.places_remaining,
        )
