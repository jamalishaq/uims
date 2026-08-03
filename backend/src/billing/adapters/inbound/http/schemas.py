"""Pydantic request and response models. They go no further than this package.

**Money is a ``Decimal`` in and a string out.** In, because ``Money`` refuses a ``float``
outright and Pydantic will hand it whatever the JSON parser produced — a body written as
``20000.10`` parses to a float in most clients, and the field type is what forces the exact
read. Out, because a two-decimal string is what a bursary statement says and a JSON number is
something a client can print back with a rounding error in it.

**There is no schema for the webhook body.** That route takes the raw request bytes: the HMAC
covers exactly what arrived, and a framework that has already parsed the body into a dict has
destroyed the thing being verified. See ``router.py``.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from billing.application.views import (
    AccountStatementView,
    ChargeAllocationView,
    ChargeView,
    IntentOutcomeView,
    PaymentConfirmedView,
    PaymentInitiatedView,
    PaymentIntentView,
    PaymentOutcomeView,
    PaymentRecordedView,
    PaymentView,
)


class ChargeResponse(BaseModel):
    """One demand for payment and how much of it has been met."""

    kind: str
    session_id: str
    amount: str
    allocated: str
    outstanding: str
    is_settled: bool
    gates_matriculation: bool

    @classmethod
    def of(cls, view: ChargeView) -> "ChargeResponse":
        return cls(**vars(view))


class PaymentResponse(BaseModel):
    """Money that arrived, as the gateway reported it."""

    gateway_ref: str
    amount: str
    received_at: datetime

    @classmethod
    def of(cls, view: PaymentView) -> "PaymentResponse":
        return cls(**vars(view))


class ChargeAllocationResponse(BaseModel):
    """How much of a payment went against which charge."""

    kind: str
    session_id: str
    amount: str

    @classmethod
    def of(cls, view: ChargeAllocationView) -> "ChargeAllocationResponse":
        return cls(**vars(view))


class PaymentOutcomeResponse(BaseModel):
    """What the ledger did, tagged ``applied`` or ``duplicate_ignored``. Both are successes."""

    outcome: str
    gateway_ref: str
    allocations: tuple[ChargeAllocationResponse, ...]
    credited: str | None
    credit_balance: str | None

    @classmethod
    def of(cls, view: PaymentOutcomeView) -> "PaymentOutcomeResponse":
        return cls(
            outcome=view.outcome,
            gateway_ref=view.gateway_ref,
            allocations=tuple(map(ChargeAllocationResponse.of, view.allocations)),
            credited=view.credited,
            credit_balance=view.credit_balance,
        )


class PaymentIntentResponse(BaseModel):
    """A checkout, and where it has got to."""

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
    def of(cls, view: PaymentIntentView) -> "PaymentIntentResponse":
        return cls(**vars(view))


class IntentOutcomeResponse(BaseModel):
    """What confirming did to the intent."""

    outcome: str
    changed: bool
    intent: PaymentIntentResponse

    @classmethod
    def of(cls, view: IntentOutcomeView) -> "IntentOutcomeResponse":
        return cls(
            outcome=view.outcome,
            changed=view.changed,
            intent=PaymentIntentResponse.of(view.intent),
        )


class AccountStatementResponse(BaseModel):
    """A whole ledger. ``credit_balance`` may be non-zero — the ledger allows surplus."""

    party_id: str
    student_id: str | None
    program_id: str
    level: int
    charges: tuple[ChargeResponse, ...]
    payments: tuple[PaymentResponse, ...]
    total_charged: str
    total_paid: str
    total_allocated: str
    outstanding: str
    credit_balance: str
    acceptance_fee_settled: bool

    @classmethod
    def of(cls, view: AccountStatementView) -> "AccountStatementResponse":
        return cls(
            **(
                vars(view)
                | {
                    "charges": tuple(map(ChargeResponse.of, view.charges)),
                    "payments": tuple(map(PaymentResponse.of, view.payments)),
                }
            )
        )


class LinkStudentAccountRequest(BaseModel):
    """The matric number an existing party-id should also answer to."""

    model_config = ConfigDict(extra="forbid")

    student_id: str = Field(min_length=1, description="The matric number.")


class StudentAccountLinkedResponse(BaseModel):
    """The link, and whether it was already there."""

    party_id: str
    student_id: str
    was_already_linked: bool


class RecordPaymentRequest(BaseModel):
    """A payment that has already happened, being written down.

    This is the bursary-override path, not the gateway path. A gateway's money arrives through
    the webhook, where a signature proves who sent it; nothing proves anything about a request
    to this route, which is why it must not be reachable without authentication. See the note
    in ``router.py``.
    """

    model_config = ConfigDict(extra="forbid")

    gateway_ref: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    received_at: datetime


class PaymentRecordedResponse(BaseModel):
    """What putting the payment on the ledger did."""

    party_id: str
    outcome: PaymentOutcomeResponse
    was_duplicate: bool

    @classmethod
    def of(cls, view: PaymentRecordedView) -> "PaymentRecordedResponse":
        return cls(
            party_id=view.party_id,
            outcome=PaymentOutcomeResponse.of(view.outcome),
            was_duplicate=view.was_duplicate,
        )


class InitiatePaymentRequest(BaseModel):
    """A checkout to open.

    ``reference`` is the gateway's reference and becomes the payment's ``gateway_ref`` — one key
    across both aggregates, which is what makes the whole path idempotent without a
    de-duplication table.
    """

    model_config = ConfigDict(extra="forbid")

    party_id: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    initiated_at: datetime
    ttl_seconds: int | None = Field(
        default=None, gt=0, description="Defaults to the domain's one-hour intent TTL."
    )


class PaymentInitiatedResponse(BaseModel):
    """The opened checkout."""

    party_id: str
    intent: PaymentIntentResponse

    @classmethod
    def of(cls, view: PaymentInitiatedView) -> "PaymentInitiatedResponse":
        return cls(party_id=view.party_id, intent=PaymentIntentResponse.of(view.intent))


class PaymentConfirmedResponse(BaseModel):
    """What a confirmation did to the ledger and to the intent.

    ``amount_matched`` false is not an error: a short payment confirms the intent and leaves
    the charge outstanding, and both are true at once.
    """

    reference: str
    party_id: str
    ledger_outcome: PaymentOutcomeResponse | None
    intent_outcome: IntentOutcomeResponse
    amount_matched: bool
    was_replay: bool

    @classmethod
    def of(cls, view: PaymentConfirmedView) -> "PaymentConfirmedResponse":
        return cls(
            reference=view.reference,
            party_id=view.party_id,
            ledger_outcome=(
                None
                if view.ledger_outcome is None
                else PaymentOutcomeResponse.of(view.ledger_outcome)
            ),
            intent_outcome=IntentOutcomeResponse.of(view.intent_outcome),
            amount_matched=view.amount_matched,
            was_replay=view.was_replay,
        )


class WebhookAcceptedResponse(BaseModel):
    """The webhook was verified and handled.

    ``handled`` is false for an event this context has no opinion about — a dispute, a
    transfer, a subscription notice. Those are ignored rather than guessed at, and the
    reconciliation sweep is what makes that safe.
    """

    handled: bool
    result: PaymentConfirmedResponse | None = None


class ApplySessionFeesRequest(BaseModel):
    """The session whose fee schedule should be applied to every active account."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)


class SessionFeesAppliedResponse(BaseModel):
    """What the batch did.

    ``unpriced`` is the one to watch: those accounts have a ``(program_id, level)`` the schedule
    does not price, and they were skipped and reported rather than refused. A party with no
    session-fee charge is not financially cleared, so an entry here is a student who cannot
    register until the bursary fills the gap.
    """

    session_id: str
    charged: tuple[str, ...]
    already_charged: tuple[str, ...]
    unpriced: tuple[str, ...]
    considered: int


class ReconcileRequest(BaseModel):
    """The instant to sweep as of.

    Supplied rather than read off the clock so a sweep is reproducible and testable, which is
    the same reason ``ReconcilePaymentIntents.execute`` takes a ``datetime``.
    """

    model_config = ConfigDict(extra="forbid")

    now: datetime


class ReconciliationSweptResponse(BaseModel):
    """What the sweep found. ``confirmed`` non-empty means a lost webhook was recovered."""

    examined: int
    skipped: int
    confirmed: tuple[str, ...]
    failed: tuple[str, ...]
    abandoned: tuple[str, ...]
    pending: tuple[str, ...]
    unreachable: tuple[str, ...]
    recovered_money: bool
