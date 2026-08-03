"""Open a party's ledger when they accept an offer, and raise the two admission charges.

The moment Billing begins. CLAUDE.md section 3: the account is "created at ``OfferAccepted``
keyed by applicant_id", and on that event Billing raises "acceptance-fee charge AND
matriculation-fee charge". Both, in one transaction, on one aggregate — they belong to the
same party and the same offer, so there is no multi-aggregate flow here to sequence.

**Both charges, but only one of them gates anything.** The acceptance fee is what
``AcceptanceFeePaid`` eventually announces and what Admissions waits on; the matriculation
fee is an outstanding balance and nothing more (CLAUDE.md section 3, and section 4's "Do not
gate matriculation on the matriculation fee"). Nothing in this use case has to encode that:
the distinction is on :class:`~billing.domain.charge.ChargeKind`, and raising the pair is all
there is to do.

**Redelivery opens no second account.** The account is looked up before it is created and the
charges are idempotent on ``(kind, session)``, so a replayed ``OfferAccepted`` — which an
at-least-once bus will produce — walks the same path and changes nothing. The result says
``was_already_open`` so a caller can tell the two apart without comparing states itself.

Amounts come from the published :class:`~billing.domain.fee_schedule.FeeSchedule` and never
from the command. A caller that could state the acceptance fee could state it wrongly, and
the applicant would be gated on a figure nobody set.

The publisher is here for a rule rather than for a path that runs today: **every event the
domain hands back gets announced**. Raising a charge can settle it outright from a standing
credit balance, and while that cannot reach the *acceptance* charge as the code stands —
credit only accumulates once nothing is outstanding, and the acceptance charge is raised on an
empty ledger — a use case that dropped events on the floor because of an argument about
reachability is one refactor away from losing one.
"""

from dataclasses import dataclass

from billing.application.errors import FeeScheduleNotPublishedError
from billing.domain.account import Account
from billing.domain.charge import Charge
from billing.domain.values import ENTRY_LEVEL, Level
from billing.ports.account_repository import AccountRepositoryPort
from billing.ports.event_publisher import EventPublisherPort
from billing.ports.fee_schedule_repository import FeeScheduleRepositoryPort


@dataclass(frozen=True)
class OpenAccountForOfferCommand:
    """One accepted offer, in primitives.

    ``program_id`` is the *offered* program, which is not always the one applied for — the
    same field ``StudentMatriculated`` carries next door, and for the same reason: what the
    party is billed for is where they are going.

    ``level`` defaults rather than being required. Nothing Admissions publishes has an opinion
    about a level, and a bus adapter with nothing to fill it with should not have to invent a
    value; :data:`~billing.domain.values.ENTRY_LEVEL` is Billing's own default and a
    construction argument at every call site.
    """

    applicant_id: str
    program_id: str
    session_id: str
    level: int = ENTRY_LEVEL


@dataclass(frozen=True)
class AccountOpened:
    """The ledger as it stands after the offer, and whether it already existed."""

    party_id: str
    acceptance_charge: Charge
    matriculation_charge: Charge
    was_already_open: bool


class OpenAccountForOffer:
    """Turn an accepted offer into a ledger with two charges on it."""

    def __init__(
        self,
        accounts: AccountRepositoryPort,
        schedules: FeeScheduleRepositoryPort,
        events: EventPublisherPort,
    ) -> None:
        self._accounts = accounts
        self._schedules = schedules
        self._events = events

    def execute(self, command: OpenAccountForOfferCommand) -> AccountOpened:
        """Open the account if it is new, and make sure both admission charges stand.

        Raises:
            FeeScheduleNotPublishedError: the session has no published fees, so there is no
                acceptance fee to gate matriculation on.
            BillingError: an identifier or the level is invalid. Domain errors pass through
                untranslated — the domain already says exactly what went wrong.
        """
        schedule = self._schedules.get(command.session_id)
        if schedule is None:
            raise FeeScheduleNotPublishedError(
                f"no fee schedule is published for session {command.session_id!r}, so the "
                f"offer accepted by applicant {command.applicant_id!r} cannot be charged"
            )

        account = self._accounts.get(command.applicant_id)
        was_already_open = account is not None
        if account is None:
            account = Account.open(
                command.applicant_id,
                command.program_id,
                level=Level(command.level),
            )

        acceptance = account.raise_acceptance_fee(command.session_id, schedule.acceptance_fee)
        matriculation = account.raise_matriculation_fee(
            command.session_id, schedule.matriculation_fee
        )

        if was_already_open:
            self._accounts.save(account)
        else:
            self._accounts.add(account)

        for event in (*acceptance.events, *matriculation.events):
            self._events.publish(event)

        return AccountOpened(
            party_id=account.party_id,
            acceptance_charge=acceptance.charge,
            matriculation_charge=matriculation.charge,
            was_already_open=was_already_open,
        )
