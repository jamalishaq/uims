"""Billing says the gating acceptance fee cleared; unlock matriculation.

The only thing Admissions consumes from anybody. CLAUDE.md section 3 has said since the
first phase that this context "Consumes ``AcceptanceFeePaid(applicant_id)``"; until Billing
had a bus to publish it on and this context had a handler to receive it, that sentence
described an intention.

**Setting a flag is all it does.** It does not matriculate. That separation is CLAUDE.md
section 4's — "Do not auto-matriculate on payment" — and it is why ``Applicant`` carries
``record_acceptance_fee_paid`` and ``matriculate`` as two methods rather than one.
"""

from dataclasses import dataclass

from admissions.application.errors import ApplicantNotFoundError
from admissions.ports.applicant_repository import ApplicantRepositoryPort


@dataclass(frozen=True)
class RecordAcceptanceFeePaidCommand:
    """Who paid. The amount is Billing's business and never crosses."""

    applicant_id: str


@dataclass(frozen=True)
class AcceptanceFeeRecorded:
    """The applicant may now be matriculated.

    ``was_already_cleared`` distinguishes the first delivery from a replay, so a caller can
    tell "we just unlocked this" from "we were told again". Neither is a failure.
    """

    applicant_id: str
    was_already_cleared: bool


class RecordAcceptanceFeePaid:
    """Mark an applicant's acceptance fee as settled."""

    def __init__(self, applicants: ApplicantRepositoryPort) -> None:
        self._applicants = applicants

    async def execute(self, command: RecordAcceptanceFeePaidCommand) -> AcceptanceFeeRecorded:
        """Set the fee-cleared flag, idempotently.

        One aggregate, so there is no ordering to argue about. Redelivery is normal rather
        than exceptional — ``AcceptanceFeePaid`` is delivered at least once — and the
        aggregate absorbs it: ``record_acceptance_fee_paid`` returns without complaint when
        the flag is already set, *including* after the applicant has been matriculated. That
        no-op is checked before the terminal-state guard on purpose, so a late replay against
        a finished application does not raise at a handler that has nothing useful to do with
        the exception.

        Returns:
            AcceptanceFeeRecorded: the flag is set, and whether it already was.

        Raises:
            ApplicantNotFoundError: no application is stored under that id.
            OfferNotAcceptedError: the applicant has not accepted an offer, so owes no
                acceptance fee — a payment against them is a question for a person.
            ApplicationOutcomeFinalError: the application reached a terminal outcome without
                ever clearing the fee.
        """
        applicant = await self._applicants.get(command.applicant_id)
        if applicant is None:
            raise ApplicantNotFoundError(f"no applicant stored with id {command.applicant_id!r}")

        was_already_cleared = applicant.is_fee_cleared
        applicant.record_acceptance_fee_paid()
        await self._applicants.save(applicant)

        return AcceptanceFeeRecorded(
            applicant_id=applicant.applicant_id,
            was_already_cleared=was_already_cleared,
        )
