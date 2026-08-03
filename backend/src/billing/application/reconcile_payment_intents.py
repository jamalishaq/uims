"""Chase the checkouts that went quiet, and ask the gateway what actually happened.

This is the use case CLAUDE.md section 3 describes when it says "before abandoning, verify via
``PaymentGatewayPort.verify(reference)`` — 'webhook lost but money taken' is the stuck state
this exists to catch." Everything else in Billing waits to be told something. This one goes
and asks.

**The TTL is a reason to ask, never a reason to conclude.** An intent that has been open
longer than its TTL has told us nothing except that we have not heard back, and the two
explanations — the payer wandered off, or the callback was dropped — have opposite
consequences. So expiry selects the question and the gateway supplies the answer; nothing here
is decided by a clock. That is also why
:meth:`~billing.domain.payment_intent.PaymentIntent.abandon` demands the verification as an
argument, so a future caller cannot reach the conclusion without having asked.

**Four answers, four different things to do**, and the ones that do nothing matter as much as
the ones that act:

* *Success* — the lost webhook, found. Record the money on the ledger and confirm the intent,
  in that order and for the reason ``ConfirmPayment`` gives. The amount recorded is the
  gateway's, never the intent's.
* *Failed* — the attempt was made and did not work. Move the intent and leave the ledger alone.
* *Pending* — still in flight. **Do nothing.** Abandoning a payment the gateway is actively
  processing is the exact mistake this whole mechanism exists to prevent, and an intent left
  open costs a second look on the next sweep.
* *Unknown* — the gateway has never heard of the reference. Nobody paid; write it off.

**One unreachable gateway must not take the batch down.** Every intent is verified in its own
try, and :class:`~billing.ports.payment_gateway.PaymentGatewayUnavailableError` — the type a
client translates its exhausted retries into, per CLAUDE.md section 4 — leaves that intent
open and counts it as unreachable. The exception caught is that named type and never a bare
``Exception``, which section 4 forbids: a bug in the translation layer should surface as a
crash, not disappear into a tally.

The sweep is idempotent and safe to run as often as anybody likes. Confirming an already
confirmed intent, abandoning an already abandoned one, and re-recording a gateway reference
the ledger holds are all no-ops that this system was built to absorb.
"""

from dataclasses import dataclass, field
from datetime import datetime

from billing.application.confirm_payment import ConfirmPayment, ConfirmPaymentCommand
from billing.domain.errors import InvalidPaymentIntentError
from billing.domain.gateway import GatewayStatus, GatewayVerification
from billing.domain.payment_intent import PaymentIntent
from billing.ports.payment_gateway import PaymentGatewayPort, PaymentGatewayUnavailableError
from billing.ports.payment_intent_repository import PaymentIntentRepositoryPort


@dataclass(frozen=True)
class ReconciliationSwept:
    """What one sweep found, in the terms an operator would want it reported.

    ``confirmed`` is the figure worth an alert if it is ever anything but zero for long: each
    one is a payment this university took and would not otherwise have known about, and a
    student who could not register against a debt they had already settled.

    ``unreachable`` is not a count of failures so much as a count of unanswered questions.
    Those intents are still open and the next sweep will ask again.
    """

    examined: int
    """Intents that were open *and* past their TTL, so the gateway was asked about them."""
    skipped: int
    """Open intents still inside their TTL. Not yet anybody's business."""
    confirmed: tuple[str, ...] = ()
    """References the gateway said were paid after all. The lost webhooks, recovered."""
    failed: tuple[str, ...] = ()
    abandoned: tuple[str, ...] = ()
    pending: tuple[str, ...] = ()
    """References the gateway is still working on. Left open, deliberately."""
    unreachable: tuple[str, ...] = ()

    @property
    def recovered_money(self) -> bool:
        """Whether this sweep found a payment the webhook path had missed."""
        return bool(self.confirmed)


@dataclass
class _Tally:
    """Mutable working set for one sweep, flattened into the frozen summary at the end."""

    examined: int = 0
    skipped: int = 0
    confirmed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    abandoned: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    unreachable: list[str] = field(default_factory=list)


class ReconcilePaymentIntents:
    """Ask the gateway about every checkout that has gone quiet, and settle each one."""

    def __init__(
        self,
        intents: PaymentIntentRepositoryPort,
        gateway: PaymentGatewayPort,
        confirm_payment: ConfirmPayment,
    ) -> None:
        self._intents = intents
        self._gateway = gateway
        self._confirm_payment = confirm_payment

    def execute(self, now: datetime) -> ReconciliationSwept:
        """Sweep every open intent that has outlived its TTL as of ``now``.

        ``now`` is an argument because nothing in this system reads a clock: an instant handed
        in is an instant a test can place on either side of a boundary without waiting an
        hour, and a scheduler that wants to re-run yesterday's sweep can.
        """
        tally = _Tally()
        for intent in self._intents.all_initiated():
            if not intent.has_expired(now):
                tally.skipped += 1
                continue
            tally.examined += 1
            self._reconcile(intent, now, tally)

        return ReconciliationSwept(
            examined=tally.examined,
            skipped=tally.skipped,
            confirmed=tuple(tally.confirmed),
            failed=tuple(tally.failed),
            abandoned=tuple(tally.abandoned),
            pending=tuple(tally.pending),
            unreachable=tuple(tally.unreachable),
        )

    def _reconcile(self, intent: PaymentIntent, now: datetime, tally: _Tally) -> None:
        """Ask about one intent and act on the answer. Never raises for an unreachable gateway."""
        try:
            verification = self._gateway.verify(intent.reference)
        except PaymentGatewayUnavailableError:
            # An unanswered question, not a negative answer. The intent stays open and the
            # next sweep asks again; writing it off on the strength of a network failure is
            # exactly the conclusion this use case exists to refuse.
            tally.unreachable.append(intent.reference)
            return

        if verification.status is GatewayStatus.SUCCESS:
            self._confirm(intent, verification, now)
            tally.confirmed.append(intent.reference)
        elif verification.status is GatewayStatus.FAILED:
            self._fail(intent, now)
            tally.failed.append(intent.reference)
        elif verification.status is GatewayStatus.PENDING:
            tally.pending.append(intent.reference)
        else:
            intent.abandon(verified=verification, at=now)
            self._intents.save(intent)
            tally.abandoned.append(intent.reference)

    def _confirm(
        self, intent: PaymentIntent, verification: GatewayVerification, now: datetime
    ) -> None:
        """Bank a payment the webhook never told us about.

        Goes through ``ConfirmPayment`` rather than moving the intent here, so that the
        recovered payment takes exactly the path a webhook's would have — ledger first, same
        idempotency, same ``AcceptanceFeePaid`` if it settles the gating charge. A second way
        to bank money would be a second set of rules to keep in step.

        The amount is the gateway's own figure, and the timestamp is when the gateway says the
        money moved rather than when this sweep noticed. ``GatewayVerification`` guarantees a
        successful answer carries an amount; a gateway that omits the instant leaves the
        ledger dated by discovery, which is the honest fallback.
        """
        confirmed = verification.amount
        if confirmed is None:
            # Unreachable: GatewayVerification refuses a successful answer with no amount at
            # construction. Stated rather than asserted, because an assert can be optimised
            # away and this is the one figure that must never be guessed.
            raise InvalidPaymentIntentError(
                f"the gateway reports {intent.reference} as paid without saying how much"
            )
        self._confirm_payment.execute(
            ConfirmPaymentCommand(
                reference=intent.reference,
                paid_at=verification.paid_at or now,
                succeeded=True,
                amount=confirmed.amount,
            )
        )

    def _fail(self, intent: PaymentIntent, now: datetime) -> None:
        """Record a failure the gateway states outright. No money moved, so no ledger entry."""
        self._confirm_payment.execute(
            ConfirmPaymentCommand(
                reference=intent.reference,
                paid_at=now,
                succeeded=False,
                failure_reason="the gateway reported the attempt failed when asked directly",
            )
        )
