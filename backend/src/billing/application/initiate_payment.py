"""Open a checkout: record that this university has asked a party for money.

The other half of the pair that makes a lost webhook detectable. ``RecordPayment`` writes down
money that arrived; this writes down money that was *asked for*, so that the two can later be
compared and the gap chased. Without it a payer whose card was charged and whose callback was
dropped leaves no trace at all, and nothing can reconcile against nothing.

**It moves no money and touches no ledger.** An intent is a statement of expectation, and a
checkout that is opened and never completed — which is most of them — must leave the account
exactly as it was. The ledger hears about this only if the gateway later confirms it.

The account is checked to exist first, and that check is the whole of this use case's
judgement. Everything else is the aggregate's.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from billing.application.errors import AccountNotFoundError
from billing.domain.payment_intent import PaymentIntent
from billing.domain.values import Money
from billing.ports.account_repository import AccountRepositoryPort
from billing.ports.payment_intent_repository import PaymentIntentRepositoryPort


@dataclass(frozen=True)
class InitiatePaymentCommand:
    """One checkout about to be opened, in primitives.

    ``reference`` is the gateway's, and this system does not mint it: whatever starts the
    checkout — a frontend calling Paystack's initialize endpoint, a bursary console — gets a
    reference back and hands it here. Minting our own would mean a second identifier to
    reconcile against the one the webhook will actually quote.

    ``ttl`` is optional and defaults to Billing's own
    :data:`~billing.domain.values.DEFAULT_INTENT_TTL`, in the manner of every other default in
    this context: a construction argument, so changing it is a decision rather than an edit
    to a rule.
    """

    party_id: str
    reference: str
    amount: Decimal
    initiated_at: datetime
    ttl: timedelta | None = None


@dataclass(frozen=True)
class PaymentInitiated:
    """The checkout is on record and the gateway may now be pointed at it."""

    party_id: str
    intent: PaymentIntent


class InitiatePayment:
    """Record that a party has been asked for money under a gateway reference."""

    def __init__(
        self, accounts: AccountRepositoryPort, intents: PaymentIntentRepositoryPort
    ) -> None:
        self._accounts = accounts
        self._intents = intents

    def execute(self, command: InitiatePaymentCommand) -> PaymentInitiated:
        """Open the intent, refusing a party with no ledger to eventually credit.

        The intent is keyed by the party's *stored* id rather than the one the caller quoted,
        so an intent opened against a matric number and an account opened against an applicant
        id stay the same ledger — the repository already resolves either, and reading the
        canonical id back off the account means the confirmation path never has to resolve it
        a second time.

        Raises:
            AccountNotFoundError: nobody has opened an account for that party, so there is
                nothing for a confirmation to land on. Asking somebody for money before the
                university has charged them anything is a caller's mistake, and inventing the
                account here would create a party out of a checkout.
            DuplicateAggregateError: an intent already exists under that reference. A gateway
                reference identifies one movement of money; a second intent claiming it would
                make the ledger's idempotency key ambiguous.
            BillingError: the amount, the reference or the timestamp is invalid.
        """
        account = self._accounts.get(command.party_id)
        if account is None:
            raise AccountNotFoundError(
                f"no billing account is stored for party {command.party_id!r}, so payment "
                f"intent {command.reference!r} has nothing to be collected against"
            )

        intent = PaymentIntent.initiate(
            reference=command.reference,
            party_id=account.party_id,
            amount=Money(command.amount),
            initiated_at=command.initiated_at,
            ttl=command.ttl,
        )
        self._intents.add(intent)
        return PaymentInitiated(party_id=account.party_id, intent=intent)
