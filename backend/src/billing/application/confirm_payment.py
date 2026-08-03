"""Settle a payment intent against what the gateway says happened, and bank the money.

The use case the webhook drives, and the one place in this system where two aggregates are
touched by one request. CLAUDE.md section 4 forbids spanning them in a transaction, so they
are written in sequence — and the sequence is the entire design of this file.

**The ledger is written first, and the intent second.** The rule the existing multi-aggregate
flows follow is to order the writes so that a crash between them leaves the recoverable state,
and here the two candidates are not close:

* Ledger first, crash: the money is on the account and the intent still says ``Initiated``.
  The next reconciliation sweep picks it up, asks the gateway, is told the payment succeeded,
  re-records it — straight into the ledger's existing duplicate-reference no-op — and confirms
  the intent. **The system heals itself and nobody is billed twice.**
* Intent first, crash: the intent says ``Confirmed`` over an account that never received the
  money. The sweep will never look at it again, because it only chases intents that are still
  open. A student is short on their ledger and nothing in the system knows.

The second is not a failure that gets noticed late; it is a failure that never gets noticed.
So: ledger, then intent. Both steps are individually idempotent, which is what makes replaying
the whole request free.

**A gateway that contradicts itself banks the money and then raises**, and that follows from
the same principle rather than being an exception to it. If a reference reported failed is
later reported succeeded, money has left somebody's account, and the ledger is the university's
record of money it received — so it is recorded. What cannot be resolved here is which of the
gateway's two statements it meant, and that is what ``PaymentIntentFinalError`` surfaces for a
person. Refusing before the ledger write would keep the intent tidy at the cost of losing the
payment, which is the wrong trade: an untidy intent is a question, and unrecorded money is a
student who cannot register against a debt they have settled.

Note that this is only reachable when the gateway states two different things about one
reference. A payment the gateway reports as *failed* never touches the ledger at all — that
branch returns before any of this.

**It composes ``RecordPayment`` rather than reaching the account itself.** CLAUDE.md section 3
requires that "the gateway is one inbound adapter calling ``RecordPayment``" and that the use
case stay gateway-agnostic; going around it here would put a second way for money to reach a
ledger, and the two would drift the first time one of them grew a rule.

**The party is read off the intent, never off the payload.** A verified signature proves the
gateway sent the request. It does not prove the gateway is right about whose money this is,
and this system does not need it to be: it opened the checkout, so it already knows. A
reference with no intent behind it is refused outright rather than credited to whoever the
body names.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from billing.application.errors import PaymentIntentNotFoundError
from billing.application.record_payment import RecordPayment, RecordPaymentCommand
from billing.domain.errors import InvalidPaymentIntentError
from billing.domain.outcomes import PaymentOutcome
from billing.domain.payment_intent import IntentOutcome, PaymentIntent, PaymentIntentConfirmed
from billing.domain.values import Money
from billing.ports.payment_intent_repository import PaymentIntentRepositoryPort


@dataclass(frozen=True)
class ConfirmPaymentCommand:
    """What a gateway has reported about one reference, in primitives.

    ``amount`` is required when ``succeeded`` and meaningless otherwise, because a failed
    attempt moved nothing. It is a ``Decimal`` and never a ``float``:
    :class:`~billing.domain.values.Money` refuses a float outright, so an adapter that read a
    gateway's JSON number carelessly fails at the boundary rather than three decimal places
    later, in a total nobody can reconcile.

    A success without an amount is refused *here*, at construction, rather than part-way
    through :meth:`ConfirmPayment.execute` — the same rule the entities follow, that a thing
    must never be constructible into a state it cannot be acted on in. Half a confirmation
    applied before the refusal would be the worst of both.
    """

    reference: str
    paid_at: datetime
    succeeded: bool
    amount: Decimal | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.succeeded and self.amount is None:
            raise InvalidPaymentIntentError(
                f"reference {self.reference!r} was reported successful without an amount; "
                "the ledger records what the gateway confirms, so there would be nothing "
                "to record"
            )


@dataclass(frozen=True)
class PaymentConfirmed:
    """What became of the report: on the ledger, and on the intent.

    ``ledger_outcome`` is ``None`` for a failed attempt, which is the honest answer — the
    ledger was not consulted, because nothing arrived to record.

    ``was_replay`` is how a caller tells a first delivery from a webhook retry without
    inspecting outcome types. Both are successes. Note that it is read off the *intent*: a
    retry finds the intent already confirmed and the ledger already holding the reference, and
    the two agree because they share the reference as their key.
    """

    reference: str
    party_id: str
    ledger_outcome: PaymentOutcome | None
    intent_outcome: IntentOutcome
    amount_matched: bool
    was_replay: bool


class ConfirmPayment:
    """Apply a gateway's report to the intent it names, banking any money it confirms."""

    def __init__(self, intents: PaymentIntentRepositoryPort, record_payment: RecordPayment) -> None:
        self._intents = intents
        self._record_payment = record_payment

    async def execute(self, command: ConfirmPaymentCommand) -> PaymentConfirmed:
        """Bank the money if there is any, then move the intent.

        Raises:
            PaymentIntentNotFoundError: this university never opened a checkout under that
                reference. Nothing is written, and the mismatch is left for a human.
            PaymentIntentFinalError: the gateway is contradicting an answer it already gave —
                reporting a failure it had called a success, or the reverse. In the second
                case the money has already reached the ledger by the time this is raised, and
                that is deliberate: money that moved is recorded whatever the intent's state,
                and it is the contradiction, not the payment, that needs a person.
            AccountNotFoundError: the intent names a party whose account has since vanished.
            BillingError: the amount, the reference or the timestamp is invalid.
        """
        intent = await self._intents.get(command.reference)
        if intent is None:
            raise PaymentIntentNotFoundError(
                f"no payment intent was opened under reference {command.reference!r}, so there "
                "is no party to credit; the payload's own account of whose money this is "
                "is not evidence"
            )

        if not command.succeeded or command.amount is None:
            return await self._record_failure(intent, command)

        # The ledger first. See this module's docstring: a crash after this line is healed by
        # the next sweep, and a crash after the intent moves would never be noticed at all.
        recorded = await self._record_payment.execute(
            RecordPaymentCommand(
                party_id=intent.party_id,
                gateway_ref=intent.reference,
                amount=command.amount,
                received_at=command.paid_at,
            )
        )

        outcome = intent.confirm(amount=Money(command.amount), at=command.paid_at)
        if outcome.changed:
            await self._intents.save(intent)

        return PaymentConfirmed(
            reference=intent.reference,
            party_id=intent.party_id,
            ledger_outcome=recorded.outcome,
            intent_outcome=outcome,
            amount_matched=(
                outcome.amount_matched
                if isinstance(outcome, PaymentIntentConfirmed)
                else intent.amount_matched
            ),
            was_replay=not outcome.changed,
        )

    async def _record_failure(
        self, intent: PaymentIntent, command: ConfirmPaymentCommand
    ) -> PaymentConfirmed:
        """A reported failure moves the intent and leaves the ledger completely alone."""
        outcome = intent.fail(
            command.failure_reason or "the gateway reported the payment did not succeed",
            at=command.paid_at,
        )
        if outcome.changed:
            await self._intents.save(intent)
        return PaymentConfirmed(
            reference=intent.reference,
            party_id=intent.party_id,
            ledger_outcome=None,
            intent_outcome=outcome,
            amount_matched=False,
            was_replay=not outcome.changed,
        )
