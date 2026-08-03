"""Billing domain layer.

Owns the university's answer to "what does this person owe, and what have they paid". One
``Account`` per party, keyed by a neutral party-id, holding one continuous ledger from the
acceptance fee onward — and three invariants that are the reason this context exists as a
context rather than as a column somewhere: a gateway reference is applied exactly once, a
charge is raised exactly once per ``(kind, session)``, and money nobody was waiting for
becomes a credit balance instead of an error.

**No opinion about clearance lives here.** Whether a student may register is a rule about
percentages of a session fee, and CLAUDE.md section 3 puts it entirely behind
``FinancialClearancePort`` — in an adapter, so that changing the percentages changes one file.
This package answers with amounts and settled/unsettled charges, and lets that adapter do the
comparing.

**No opinion about matriculation lives here either.** Settling the gating charge produces
``AcceptanceFeePaid``, a past-tense fact. What Admissions does with it is Admissions'
business, and "Do not auto-matriculate on payment" (CLAUDE.md section 4) is the whole reason
the fact is stated rather than the action taken.

Stdlib only: no persistence, no ports, no HTTP reaches this package. ``decimal`` and never
``float`` — see :class:`~billing.domain.values.Money`, which refuses a float outright, because
a bursary reconciling against a payment gateway would find the difference.

Two Billing-owned defaults live here as named constants rather than as literals inside rules,
in the manner of Student Profile's matric format and Enrollment's 24-unit cap:
:data:`~billing.domain.values.ENTRY_LEVEL`, the level an account is booked at because no event
carries one, and the allocation order in :class:`~billing.domain.account.Account` — gating
charge first. Fee *amounts* are deliberately not here at all: they are institutional facts
(CLAUDE.md section 6), and they arrive on a published :class:`FeeSchedule`.
"""

from billing.domain.account import Account
from billing.domain.charge import Charge, ChargeKind
from billing.domain.errors import (
    BillingError,
    InvalidAmountError,
    InvalidChargeError,
    InvalidFeeScheduleError,
    InvalidLevelError,
    InvalidPaymentError,
    InvalidPaymentIntentError,
    MissingIdentifierError,
    PartyAlreadyLinkedError,
    PaymentIntentFinalError,
)
from billing.domain.events import AcceptanceFeePaid, DomainEvent
from billing.domain.fee_schedule import FeeSchedule, SessionFeeLine
from billing.domain.gateway import GatewayStatus, GatewayVerification
from billing.domain.outcomes import (
    ChargeAllocation,
    ChargeAlreadyRaised,
    ChargeOutcome,
    ChargeRaised,
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
    PaymentIntentStatus,
)
from billing.domain.values import (
    DEFAULT_INTENT_TTL,
    ENTRY_LEVEL,
    LEVEL_STEP,
    MINOR_UNIT_PLACES,
    Level,
    Money,
)

__all__ = [
    "DEFAULT_INTENT_TTL",
    "ENTRY_LEVEL",
    "LEVEL_STEP",
    "MINOR_UNIT_PLACES",
    "AcceptanceFeePaid",
    "Account",
    "BillingError",
    "Charge",
    "ChargeAllocation",
    "ChargeAlreadyRaised",
    "ChargeKind",
    "ChargeOutcome",
    "ChargeRaised",
    "DomainEvent",
    "DuplicatePaymentIgnored",
    "FeeSchedule",
    "GatewayStatus",
    "GatewayVerification",
    "IntentOutcome",
    "InvalidAmountError",
    "InvalidChargeError",
    "InvalidFeeScheduleError",
    "InvalidLevelError",
    "InvalidPaymentError",
    "InvalidPaymentIntentError",
    "Level",
    "MissingIdentifierError",
    "Money",
    "PartyAlreadyLinkedError",
    "Payment",
    "PaymentApplied",
    "PaymentIntent",
    "PaymentIntentAbandoned",
    "PaymentIntentAlreadyResolved",
    "PaymentIntentConfirmed",
    "PaymentIntentFailed",
    "PaymentIntentFinalError",
    "PaymentIntentStatus",
    "PaymentOutcome",
    "SessionFeeLine",
]
