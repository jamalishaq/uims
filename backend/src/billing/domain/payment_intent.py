"""The ``PaymentIntent`` aggregate: money this university asked for, and what became of it.

**It exists to make one failure mode visible.** CLAUDE.md section 3 names it exactly: "'webhook
lost but money taken' is the stuck state this exists to catch." Without an intent, a payer
whose card is charged and whose callback never arrives leaves this system with no record of
the transaction at all — the only evidence is an absence, and nothing can reconcile against an
absence. An intent is the row that says *we asked for this*, under this reference, at this
time, and it is what a sweep can later take to the gateway and ask about.

**An intent is not money.** The ``Account`` is the ledger; this is bookkeeping about a
checkout. That separation is why :attr:`amount` and :attr:`confirmed_amount` are two fields
and not one: the first is what was asked for, the second is what the gateway says actually
moved, and CLAUDE.md section 3 requires that "the ledger records the amount the gateway
confirms, never the intent's amount". A short payment confirms the intent *and* leaves the
charge unsettled, and both of those are true at once. Nothing here refuses a mismatch —
refusing it would strand money that has genuinely left somebody's account.

**Its own aggregate, with its own repository.** Confirming a payment therefore touches two
aggregates, which CLAUDE.md section 4 forbids doing in one transaction, so
``ConfirmPayment`` orchestrates them in sequence — the ledger first, the intent second. The
ordering is chosen the way ``MakeOfferToApplicant`` and ``RegisterForCourse`` choose theirs:
so that a crash in between leaves the *recoverable* state. Crashing after the ledger write
leaves this intent ``Initiated`` with the money already recorded, and the next sweep verifies,
re-records against the ledger's existing idempotency no-op, and confirms — it heals itself.
The reverse order would leave an intent claiming to be confirmed over a ledger that never
received the money, and nothing would ever come back to check.

The join between the two aggregates is the gateway's own reference: this intent's
:attr:`reference` *is* the ``gateway_ref`` on the resulting ``Payment``. That single shared key
is what makes the whole path idempotent end to end without a de-duplication table anywhere.

**Confirmed and failed are terminal. Abandoned is not.** An abandonment is a presumption a
clock made; a confirmation is a fact the gateway stated, and a fact beats a presumption — so
money that turns out to have moved can still be recorded against the intent it was for, even
after the sweep had written it off. Failure stays terminal, because a gateway that reports one
reference failed and then reports it succeeded is contradicting itself, and choosing which
statement to believe is not a decision this aggregate can make.

Time arrives as an argument and is never read. There is no clock in this system — every
existing entity is handed the instant it should act on — and a TTL judged against a ``now``
the caller supplied is a TTL a test can put either side of a boundary without waiting.
Whether those instants carry a timezone is the adapter's business, in the same way
:func:`~billing.domain.values.require_timestamp` leaves it; mixing an aware instant with a
naive one raises out of ``datetime`` itself, which is a better error than any this file
could invent.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from billing.domain.errors import InvalidPaymentIntentError, PaymentIntentFinalError
from billing.domain.gateway import GatewayVerification
from billing.domain.values import (
    DEFAULT_INTENT_TTL,
    Money,
    require_identifier,
    require_text,
    require_timestamp,
)


class PaymentIntentStatus(Enum):
    """Where a checkout has got to. Its value is the wording a reconciliation report would use."""

    INITIATED = "initiated"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    ABANDONED = "abandoned"

    def __str__(self) -> str:
        return self.value


_FINAL_STATUSES = frozenset({PaymentIntentStatus.CONFIRMED, PaymentIntentStatus.FAILED})
"""States nothing moves out of.

``ABANDONED`` is deliberately absent. See this module's docstring: the sweep abandons on a
presumption, and a later confirmation is evidence that the presumption was wrong.
"""


# ---- outcomes ----------------------------------------------------------------------------
#
# The intent's own answers, in the shape ``billing.domain.outcomes`` uses for the account's:
# a frozen dataclass per answer and a union alias the caller must handle. They live here
# rather than in that module because its docstring scopes itself to "what
# ``Account.apply_payment`` and ``Account.raise_charge`` hand back to the caller", and these
# are a different aggregate's vocabulary.
#
# Unlike the account's outcomes, none of these carries ``events``. An intent announces
# nothing: no other context has any use for the fact that a checkout was opened or written
# off, and an event nobody consumes is wiring that can be neither right nor wrong. What the
# world hears about a payment it hears from the ledger, as ``AcceptanceFeePaid``.
#
# What they carry instead is ``changed``, which is how a use case decides whether the
# aggregate is worth saving without first asking which outcome it is holding.


@dataclass(frozen=True)
class PaymentIntentConfirmed:
    """The gateway confirmed the money moved, and this intent now records that."""

    intent: "PaymentIntent"
    confirmed_amount: Money
    """What the gateway says actually moved. The figure the ledger is given."""
    amount_matched: bool
    """Whether that equals what was asked for. ``False`` is not an error; it is a short or
    over payment, and the ledger deals with either without complaint."""
    was_revived: bool
    """Whether this confirmed an intent the sweep had already abandoned — the late webhook."""

    @property
    def changed(self) -> bool:
        return True


@dataclass(frozen=True)
class PaymentIntentFailed:
    """The gateway said the attempt did not succeed. No money moved, so no ledger entry."""

    intent: "PaymentIntent"
    reason: str

    @property
    def changed(self) -> bool:
        return True


@dataclass(frozen=True)
class PaymentIntentAbandoned:
    """The intent went quiet, the gateway was asked, and it did not report a payment.

    ``verified`` is kept because it is the evidence the abandonment rests on: months later,
    "why is this written off" has an answer that is not "a timer".
    """

    intent: "PaymentIntent"
    verified: GatewayVerification

    @property
    def changed(self) -> bool:
        return True


@dataclass(frozen=True)
class PaymentIntentAlreadyResolved:
    """This intent was already in the state it was being asked to move to. Nothing changed.

    The ordinary answer to a retrying webhook, and the sibling of
    :class:`~billing.domain.outcomes.DuplicatePaymentIgnored` one aggregate over. Not an
    error, for the same reason: at-least-once delivery is what every payment gateway worth
    using does, and a system whose normal traffic ran through error handlers would have
    somebody triaging retries at three in the morning.
    """

    intent: "PaymentIntent"

    @property
    def changed(self) -> bool:
        return False


IntentOutcome = (
    PaymentIntentConfirmed
    | PaymentIntentFailed
    | PaymentIntentAbandoned
    | PaymentIntentAlreadyResolved
)
"""Everything a transition on :class:`PaymentIntent` can answer. Callers must handle each."""


# ---- the aggregate -----------------------------------------------------------------------


class PaymentIntent:
    """One attempt to collect money from one party, and what the gateway made of it."""

    def __init__(
        self,
        reference: str,
        party_id: str,
        amount: Money,
        initiated_at: datetime,
        ttl: timedelta | None = None,
    ) -> None:
        if not isinstance(amount, Money):
            raise InvalidPaymentIntentError("intent amount must be Money")
        if amount.is_zero:
            raise InvalidPaymentIntentError(
                "an intent for nothing would consume a gateway reference and collect no money"
            )
        self._reference = require_identifier(reference, "reference")
        self._party_id = require_identifier(party_id, "party_id")
        self._amount = amount
        self._initiated_at = require_timestamp(initiated_at, "initiated_at")
        self._ttl = self._require_ttl(ttl)
        self._status = PaymentIntentStatus.INITIATED
        self._confirmed_amount: Money | None = None
        self._resolved_at: datetime | None = None
        self._failure_reason: str | None = None

    @classmethod
    def initiate(
        cls,
        reference: str,
        party_id: str,
        amount: Money,
        *,
        initiated_at: datetime,
        ttl: timedelta | None = None,
    ) -> "PaymentIntent":
        """Open a checkout for ``amount`` under the gateway's ``reference``.

        The reference is the gateway's, not one this system minted, and it is checked only for
        non-emptiness — the same treatment
        :func:`~billing.domain.values.require_identifier` gives every foreign id, and for the
        stronger reason it states: a ledger that parsed a reference would break the day a
        second gateway was added.
        """
        return cls(reference, party_id, amount, initiated_at, ttl)

    @staticmethod
    def _require_ttl(ttl: timedelta | None) -> timedelta:
        if ttl is None:
            return DEFAULT_INTENT_TTL
        if not isinstance(ttl, timedelta):
            raise InvalidPaymentIntentError("ttl must be a timedelta")
        if ttl <= timedelta(0):
            raise InvalidPaymentIntentError(
                f"a ttl of {ttl} would make every intent stale the moment it was opened"
            )
        return ttl

    # ---- reading ----

    @property
    def reference(self) -> str:
        """The gateway's reference, and the key this intent is stored under.

        Also the ``gateway_ref`` of the ``Payment`` that confirming this produces. One key
        across both aggregates is what makes the confirmation path idempotent end to end.
        """
        return self._reference

    @property
    def party_id(self) -> str:
        """Whose ledger a confirmation lands on.

        Read off the intent and never off a webhook payload. A valid signature proves the
        gateway sent the request; it does not prove the gateway is right about whose money
        this is, and this system already knows, because it was this system that asked.
        """
        return self._party_id

    @property
    def amount(self) -> Money:
        """What was asked for. Never what the ledger records."""
        return self._amount

    @property
    def confirmed_amount(self) -> Money | None:
        """What the gateway says moved, or ``None`` while nothing has been confirmed."""
        return self._confirmed_amount

    @property
    def initiated_at(self) -> datetime:
        return self._initiated_at

    @property
    def ttl(self) -> timedelta:
        return self._ttl

    @property
    def expires_at(self) -> datetime:
        """When this intent becomes a candidate for reconciliation. Not when it dies."""
        return self._initiated_at + self._ttl

    @property
    def status(self) -> PaymentIntentStatus:
        return self._status

    @property
    def resolved_at(self) -> datetime | None:
        """When it stopped being open, or ``None`` while it still is."""
        return self._resolved_at

    @property
    def failure_reason(self) -> str | None:
        """What the gateway said went wrong, or ``None`` if it never said so."""
        return self._failure_reason

    @property
    def is_final(self) -> bool:
        """Whether this intent has reached a state it can never move out of.

        Abandoned is not one of them, which is the whole of this aggregate's opinion about
        late webhooks.
        """
        return self._status in _FINAL_STATUSES

    @property
    def is_open(self) -> bool:
        """Whether the gateway has yet to say anything about this reference."""
        return self._status is PaymentIntentStatus.INITIATED

    @property
    def amount_matched(self) -> bool:
        """Whether what was confirmed equals what was asked for. ``False`` while unconfirmed."""
        return self._confirmed_amount is not None and self._confirmed_amount == self._amount

    def has_expired(self, now: datetime) -> bool:
        """Whether this intent has been open longer than its TTL allows.

        Strictly after :attr:`expires_at`: an intent at exactly its expiry has used all the
        time it was given and not one instant more, and a boundary that swept it would be
        judging it by a clock's rounding.

        Says nothing about whether money moved — only that it is worth asking the gateway.
        A confirmed, failed or abandoned intent has already been answered and is never stale.
        """
        require_timestamp(now, "now")
        return self.is_open and now > self.expires_at

    # ---- transitions ----

    def confirm(self, *, amount: Money, at: datetime) -> IntentOutcome:
        """Record that the gateway confirmed ``amount`` against this reference.

        ``amount`` is the gateway's figure and is stored as given. It is not compared against
        :attr:`amount` in order to be refused — only in order to be *reported*, through
        :attr:`PaymentIntentConfirmed.amount_matched`, because "the ledger records the amount
        the gateway confirms" (CLAUDE.md section 3) and a mismatch is a part-paid charge
        rather than a fault. Money that has left somebody's account is a fact whatever this
        intent expected.

        An intent already confirmed answers :class:`PaymentIntentAlreadyResolved` and changes
        nothing, including when the replay quotes a different amount: the reference is the
        identity of the movement of money, exactly as it is on the ledger, and the discrepancy
        is a reconciliation question rather than a second confirmation.

        An **abandoned** intent is confirmed and reports ``was_revived``. A **failed** one
        refuses.

        Raises:
            PaymentIntentFinalError: this reference was already reported failed. Note the
                sequencing: ``ConfirmPayment`` writes the ledger before it gets here, so a
                gateway that contradicts itself puts the money on the account and *then*
                raises. That is the honest result — the money moved, so it is recorded, and
                the contradiction is surfaced rather than absorbed.
        """
        if not isinstance(amount, Money):
            raise InvalidPaymentIntentError("confirmed amount must be Money")
        require_timestamp(at, "at")

        if self._status is PaymentIntentStatus.CONFIRMED:
            return PaymentIntentAlreadyResolved(intent=self)
        self._reject_if_final()

        was_revived = self._status is PaymentIntentStatus.ABANDONED
        self._status = PaymentIntentStatus.CONFIRMED
        self._confirmed_amount = amount
        self._resolved_at = at
        return PaymentIntentConfirmed(
            intent=self,
            confirmed_amount=amount,
            amount_matched=amount == self._amount,
            was_revived=was_revived,
        )

    def fail(self, reason: str, *, at: datetime) -> IntentOutcome:
        """Record that the gateway reported the attempt did not succeed.

        No money moved, so nothing reaches the ledger. An abandoned intent may be failed — a
        stated fact replacing a presumption is an improvement — and a second failure report is
        a no-op.

        Raises:
            PaymentIntentFinalError: this reference was already confirmed. The gateway is
                contradicting itself, and the money is already on the ledger.
        """
        reason = require_text(reason, "reason")
        require_timestamp(at, "at")

        if self._status is PaymentIntentStatus.FAILED:
            return PaymentIntentAlreadyResolved(intent=self)
        self._reject_if_final()

        self._status = PaymentIntentStatus.FAILED
        self._resolved_at = at
        self._failure_reason = reason
        return PaymentIntentFailed(intent=self, reason=reason)

    def abandon(self, *, verified: GatewayVerification, at: datetime) -> IntentOutcome:
        """Write this intent off as never having been paid.

        **The evidence is a required argument, and that is the point.** CLAUDE.md section 3
        says to "verify via ``PaymentGatewayPort.verify(reference)``" before abandoning; a
        rule kept that way in a use case is a rule the next caller can skip, so it is kept
        here instead — an abandonment is not expressible without the gateway's answer in hand.

        The answer must also be about *this* reference and must not be a success. A gateway
        still working on the reference is refused too: ``PENDING`` is not an answer, and
        writing off a payment that is about to complete is the one mistake reconciliation
        exists to avoid.

        Abandoning an already-abandoned intent is a no-op, so a sweep that runs twice is free.

        Raises:
            InvalidPaymentIntentError: the verification is for another reference, reports
                success, or is inconclusive.
            PaymentIntentFinalError: the intent is already confirmed or failed.
        """
        if not isinstance(verified, GatewayVerification):
            raise InvalidPaymentIntentError(
                "an intent may only be abandoned against a GatewayVerification; "
                "CLAUDE.md section 3 requires the gateway to be asked first"
            )
        if verified.reference != self._reference:
            raise InvalidPaymentIntentError(
                f"verification is for {verified.reference!r}, not for intent "
                f"{self._reference!r}; evidence about another payment proves nothing here"
            )
        if verified.succeeded:
            raise InvalidPaymentIntentError(
                f"the gateway reports {self._reference} as paid; an intent the money arrived "
                "for is confirmed, never abandoned"
            )
        if not verified.is_conclusive:
            raise InvalidPaymentIntentError(
                f"the gateway is still processing {self._reference}; abandoning now would race "
                "a payment that may yet complete, which is the stuck state this check exists "
                "to avoid"
            )
        require_timestamp(at, "at")

        if self._status is PaymentIntentStatus.ABANDONED:
            return PaymentIntentAlreadyResolved(intent=self)
        self._reject_if_final()

        self._status = PaymentIntentStatus.ABANDONED
        self._resolved_at = at
        return PaymentIntentAbandoned(intent=self, verified=verified)

    def _reject_if_final(self) -> None:
        if self.is_final:
            raise PaymentIntentFinalError(
                f"payment intent {self._reference} is {self._status} and cannot change"
            )

    def __repr__(self) -> str:
        return (
            f"PaymentIntent(reference={self._reference!r}, party_id={self._party_id!r}, "
            f"amount={self._amount}, status={self._status.name}, "
            f"confirmed={self._confirmed_amount})"
        )
