"""Record money that a gateway confirmed, and announce anything settling it made true.

The one use case money enters this system through. CLAUDE.md section 3: "The gateway is one
inbound adapter calling ``RecordPayment``; additional gateways or a manual bursary override
are future adapters to the same use case. Keep ``RecordPayment`` and the Account
gateway-agnostic." So this class takes a reference, an amount and a timestamp — three
primitives that any gateway, and equally a bursary clerk's console, can supply — and it names
none of them.

**It does not verify anything.** Phase 5.3's webhook adapter checks the gateway's signature
*before* the payload reaches any use case (CLAUDE.md section 3, and section 4 flags the path
as security-sensitive). By the time execution arrives here the money is a fact; what is left
is to write it down and allocate it.

**The amount is the one that arrived.** Not an intent's amount, not a charge's amount: "the
ledger records the amount the gateway confirms". The command takes a ``Decimal`` and
:class:`~billing.domain.values.Money` refuses a ``float`` outright, so an adapter that reads a
gateway's JSON number carelessly fails here rather than three decimal places later.

**Saving follows the ledger, not the call.** A duplicate reference leaves the aggregate
untouched, so nothing is written and nothing is published — which is what makes a retrying
webhook free rather than merely harmless. The claim "the same ``gateway_ref`` applied twice
changes the ledger once" is testable at exactly this seam.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from billing.application.errors import AccountNotFoundError
from billing.domain.events import DomainEvent
from billing.domain.outcomes import PaymentApplied, PaymentOutcome
from billing.domain.values import Money
from billing.ports.account_repository import AccountRepositoryPort
from billing.ports.event_publisher import EventPublisherPort


@dataclass(frozen=True)
class RecordPaymentCommand:
    """One confirmed payment, in primitives.

    ``party_id`` is whichever id the payer is known by — an applicant id before matriculation,
    a matric number after. The repository resolves either, so a gateway that has been quoting
    a matric number since the student got one does not have to know there was ever another id.
    """

    party_id: str
    gateway_ref: str
    amount: Decimal
    received_at: datetime


@dataclass(frozen=True)
class PaymentRecorded:
    """What the ledger did with the payment.

    ``was_duplicate`` is how a caller tells a first delivery from a webhook retry without
    inspecting the outcome type. Both are successes: at-least-once delivery is the normal
    behaviour of every payment gateway worth using.
    """

    party_id: str
    outcome: PaymentOutcome
    was_duplicate: bool
    published: tuple[DomainEvent, ...]


class RecordPayment:
    """Put a confirmed payment on a party's ledger."""

    def __init__(self, accounts: AccountRepositoryPort, events: EventPublisherPort) -> None:
        self._accounts = accounts
        self._events = events

    def execute(self, command: RecordPaymentCommand) -> PaymentRecorded:
        """Apply the payment, saving and announcing only if the ledger actually changed.

        Raises:
            AccountNotFoundError: money arrived for a party with no ledger. Opening one here
                would invent a party out of a gateway reference; the mismatch is left visible
                for a human to reconcile.
            BillingError: the amount, the reference or the timestamp is invalid. Domain errors
                pass through untranslated.
        """
        account = self._accounts.get(command.party_id)
        if account is None:
            raise AccountNotFoundError(
                f"no billing account is stored for party {command.party_id!r}, so payment "
                f"{command.gateway_ref!r} cannot be recorded"
            )

        outcome = account.apply_payment(
            gateway_ref=command.gateway_ref,
            amount=Money(command.amount),
            received_at=command.received_at,
        )

        applied = isinstance(outcome, PaymentApplied)
        if applied:
            self._accounts.save(account)
            for event in outcome.events:
                self._events.publish(event)

        return PaymentRecorded(
            party_id=account.party_id,
            outcome=outcome,
            was_duplicate=not applied,
            published=outcome.events,
        )
