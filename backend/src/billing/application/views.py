"""Primitives-shaped projections of what this context's use cases return.

The context with the most to flatten, and the one where getting it wrong costs the most.

**Money crosses as a string, always.** ``Money`` refuses a ``float`` outright at construction —
"an amount that cannot be read exactly must not be written to a ledger" — and a view that handed
a transport a float would put back exactly the imprecision the value object exists to keep out.
Two decimal places, as ``str(Money)`` renders them, is what a bursary statement says and what a
client should parse as a decimal at the other end.

**``PaymentInitiated`` and ``PaymentConfirmed`` reach the live aggregate**, through
``PaymentInitiated.intent`` and through every arm of ``IntentOutcome``. Those are the two places
in the system where a DTO wrapper does not actually protect anything, and projecting them here
is what closes it: past this module nothing holds an object that can ``confirm()`` an intent.

**The outcome unions become a tagged shape.** ``PaymentOutcome`` and ``IntentOutcome`` are
discriminated by ``isinstance`` and nothing else — there is no tag field to serialise. So the
tag is added here, once, rather than in each transport that has to tell an applied payment from
an ignored duplicate.
"""

from dataclasses import dataclass
from datetime import datetime

from billing.application.confirm_payment import PaymentConfirmed
from billing.application.initiate_payment import PaymentInitiated
from billing.application.open_account_for_offer import AccountOpened
from billing.application.read_account import AccountStatement
from billing.application.record_payment import PaymentRecorded
from billing.domain.charge import Charge
from billing.domain.outcomes import (
    ChargeAllocation,
    DuplicatePaymentIgnored,
    PaymentApplied,
    PaymentOutcome,
)
from billing.domain.payment import Payment
from billing.domain.payment_intent import (
    IntentOutcome,
    PaymentIntent,
    PaymentIntentAbandoned,
    PaymentIntentAlreadyResolved,
    PaymentIntentConfirmed,
    PaymentIntentFailed,
)


@dataclass(frozen=True)
class ChargeView:
    """One demand for payment and how much of it has been met."""

    kind: str
    session_id: str
    amount: str
    allocated: str
    outstanding: str
    is_settled: bool
    gates_matriculation: bool

    @classmethod
    def of(cls, charge: Charge) -> "ChargeView":
        return cls(
            kind=charge.kind.value,
            session_id=charge.session_id,
            amount=str(charge.amount),
            allocated=str(charge.allocated),
            outstanding=str(charge.outstanding),
            is_settled=charge.is_settled,
            gates_matriculation=charge.kind.gates_matriculation,
        )


@dataclass(frozen=True)
class PaymentView:
    """Money that arrived, as the gateway reported it."""

    gateway_ref: str
    amount: str
    received_at: datetime

    @classmethod
    def of(cls, payment: Payment) -> "PaymentView":
        return cls(
            gateway_ref=payment.gateway_ref,
            amount=str(payment.amount),
            received_at=payment.received_at,
        )


@dataclass(frozen=True)
class ChargeAllocationView:
    """How much of a payment went against which charge."""

    kind: str
    session_id: str
    amount: str

    @classmethod
    def of(cls, allocation: ChargeAllocation) -> "ChargeAllocationView":
        return cls(
            kind=allocation.kind.value,
            session_id=allocation.session_id,
            amount=str(allocation.amount),
        )


@dataclass(frozen=True)
class PaymentOutcomeView:
    """What the ledger did with a payment, tagged so a caller need not guess.

    ``outcome`` is ``"applied"`` or ``"duplicate_ignored"``. Both are successes — a retrying
    webhook is normal, not an error — and the difference is whether anything was written.
    """

    outcome: str
    gateway_ref: str
    allocations: tuple[ChargeAllocationView, ...]
    credited: str | None
    credit_balance: str | None

    @classmethod
    def of(cls, outcome: PaymentOutcome) -> "PaymentOutcomeView":
        if isinstance(outcome, PaymentApplied):
            return cls(
                outcome="applied",
                gateway_ref=outcome.payment.gateway_ref,
                allocations=tuple(
                    ChargeAllocationView.of(allocation) for allocation in outcome.allocations
                ),
                credited=str(outcome.credited),
                credit_balance=str(outcome.credit_balance),
            )
        if isinstance(outcome, DuplicatePaymentIgnored):
            return cls(
                outcome="duplicate_ignored",
                gateway_ref=outcome.gateway_ref,
                allocations=(),
                credited=None,
                credit_balance=None,
            )
        raise TypeError(f"unhandled payment outcome {type(outcome).__name__}")


@dataclass(frozen=True)
class PaymentIntentView:
    """A checkout, and where it has got to. Carries no way to move it on."""

    reference: str
    party_id: str
    amount: str
    confirmed_amount: str | None
    status: str
    initiated_at: datetime
    expires_at: datetime
    resolved_at: datetime | None
    failure_reason: str | None

    @classmethod
    def of(cls, intent: PaymentIntent) -> "PaymentIntentView":
        return cls(
            reference=intent.reference,
            party_id=intent.party_id,
            amount=str(intent.amount),
            confirmed_amount=None
            if intent.confirmed_amount is None
            else str(intent.confirmed_amount),
            status=intent.status.value,
            initiated_at=intent.initiated_at,
            expires_at=intent.expires_at,
            resolved_at=intent.resolved_at,
            failure_reason=intent.failure_reason,
        )


_INTENT_OUTCOME_TAGS: dict[type, str] = {
    PaymentIntentConfirmed: "confirmed",
    PaymentIntentFailed: "failed",
    PaymentIntentAbandoned: "abandoned",
    PaymentIntentAlreadyResolved: "already_resolved",
}


@dataclass(frozen=True)
class IntentOutcomeView:
    """What confirming did to the intent, tagged, with the intent itself projected.

    ``changed`` is the domain's own answer to "was this worth saving", carried through rather
    than re-derived from the tag: all four outcomes answer it, and the day a fifth is added
    the tag map above fails loudly while a reconstructed boolean would quietly be wrong.
    """

    outcome: str
    changed: bool
    intent: PaymentIntentView

    @classmethod
    def of(cls, outcome: IntentOutcome) -> "IntentOutcomeView":
        tag = _INTENT_OUTCOME_TAGS.get(type(outcome))
        if tag is None:
            raise TypeError(f"unhandled intent outcome {type(outcome).__name__}")
        return cls(
            outcome=tag,
            changed=outcome.changed,
            intent=PaymentIntentView.of(outcome.intent),
        )


@dataclass(frozen=True)
class AccountStatementView:
    """A whole ledger, flat: what was charged, what arrived, and what is left.

    ``credit_balance`` is never assumed to be zero. The ledger allows surplus — CLAUDE.md
    section 3 — and a client that treated an overpayment as an error would be reporting a
    state the domain deliberately permits.
    """

    party_id: str
    student_id: str | None
    program_id: str
    level: int
    charges: tuple[ChargeView, ...]
    payments: tuple[PaymentView, ...]
    total_charged: str
    total_paid: str
    total_allocated: str
    outstanding: str
    credit_balance: str
    acceptance_fee_settled: bool

    @classmethod
    def of(cls, statement: AccountStatement) -> "AccountStatementView":
        return cls(
            party_id=statement.party_id,
            student_id=statement.student_id,
            program_id=statement.program_id,
            level=statement.level.value,
            charges=tuple(ChargeView.of(charge) for charge in statement.charges),
            payments=tuple(PaymentView.of(payment) for payment in statement.payments),
            total_charged=str(statement.total_charged),
            total_paid=str(statement.total_paid),
            total_allocated=str(statement.total_allocated),
            outstanding=str(statement.outstanding),
            credit_balance=str(statement.credit_balance),
            acceptance_fee_settled=statement.acceptance_fee_settled,
        )


@dataclass(frozen=True)
class AccountOpenedView:
    """The two charges an accepted offer raises."""

    party_id: str
    acceptance_charge: ChargeView
    matriculation_charge: ChargeView
    was_already_open: bool

    @classmethod
    def of(cls, opened: AccountOpened) -> "AccountOpenedView":
        return cls(
            party_id=opened.party_id,
            acceptance_charge=ChargeView.of(opened.acceptance_charge),
            matriculation_charge=ChargeView.of(opened.matriculation_charge),
            was_already_open=opened.was_already_open,
        )


@dataclass(frozen=True)
class PaymentRecordedView:
    """What putting a payment on a ledger did."""

    party_id: str
    outcome: PaymentOutcomeView
    was_duplicate: bool

    @classmethod
    def of(cls, recorded: PaymentRecorded) -> "PaymentRecordedView":
        return cls(
            party_id=recorded.party_id,
            outcome=PaymentOutcomeView.of(recorded.outcome),
            was_duplicate=recorded.was_duplicate,
        )


@dataclass(frozen=True)
class PaymentInitiatedView:
    """A checkout that has been opened."""

    party_id: str
    intent: PaymentIntentView

    @classmethod
    def of(cls, initiated: PaymentInitiated) -> "PaymentInitiatedView":
        return cls(
            party_id=initiated.party_id,
            intent=PaymentIntentView.of(initiated.intent),
        )


@dataclass(frozen=True)
class PaymentConfirmedView:
    """What a confirmation did to both aggregates.

    ``ledger_outcome`` is ``None`` when the gateway reported a failure: that branch never
    touches the ledger, and reporting an empty allocation instead would suggest it had.

    ``amount_matched`` being false is not an error. A short payment confirms the intent *and*
    leaves the charge outstanding; both are true at once and neither is refused.
    """

    reference: str
    party_id: str
    ledger_outcome: PaymentOutcomeView | None
    intent_outcome: IntentOutcomeView
    amount_matched: bool
    was_replay: bool

    @classmethod
    def of(cls, confirmed: PaymentConfirmed) -> "PaymentConfirmedView":
        return cls(
            reference=confirmed.reference,
            party_id=confirmed.party_id,
            ledger_outcome=(
                None
                if confirmed.ledger_outcome is None
                else PaymentOutcomeView.of(confirmed.ledger_outcome)
            ),
            intent_outcome=IntentOutcomeView.of(confirmed.intent_outcome),
            amount_matched=confirmed.amount_matched,
            was_replay=confirmed.was_replay,
        )
