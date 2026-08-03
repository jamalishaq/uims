"""Billing application layer.

Eight use cases, and the shape of the set says what this context is. Two are driven by events
from elsewhere and raise charges (:class:`OpenAccountForOffer`, :class:`ApplySessionFees`);
one is driven by money arriving and is the only way money ever gets onto a ledger
(:class:`RecordPayment`); one is an administrative act nothing publishes yet
(:class:`LinkStudentAccount`); one only reads (:class:`ReadAccount`).

Three more make up the gateway path, and they are a matched set rather than three additions.
:class:`InitiatePayment` records that money was asked for; :class:`ConfirmPayment` settles
that record against what the gateway reports and banks anything that moved;
:class:`ReconcilePaymentIntents` chases the ones that went quiet. The middle one is the only
one a webhook drives, and none of them reaches an ``Account`` directly — they compose
:class:`RecordPayment`, because CLAUDE.md section 3 requires that "the gateway is one inbound
adapter calling ``RecordPayment``" and a second route for money onto a ledger would be a
second set of rules to keep in step.

That there is no ninth is still the point. No "recompute balance" — a balance is derived from
the charges and payments on read, so there is no stored figure to fall out of step. No "settle
charge", because charges settle by being paid rather than by being marked. No "clear student
for registration", because that judgement is a rule behind ``FinancialClearancePort`` and not
a thing anybody does. No "expire intent", because a clock decides nothing here: an expired
intent is a question for the gateway, and the answer is what moves it. And no refunds: a
deferred admin use case (CLAUDE.md section 3), which when it arrives will be entries on the
ledger rather than a subtraction.

Orchestration only. Every rule these use cases appear to apply belongs to the domain: which
charge a payment goes to, whether a gateway reference has been seen, whether an overpayment is
allowed, whether an intent may still move. What is decided here is what a use case is allowed
to decide — that an unpriced account is skipped rather than failed, that a session with no
schedule at all stops the batch, that money for a party with no ledger is refused rather than
made to fit, and in which *order* the ledger and an intent are written when one request has to
touch both.
"""

from billing.application.apply_session_fees import ApplySessionFees, SessionFeesApplied
from billing.application.confirm_payment import (
    ConfirmPayment,
    ConfirmPaymentCommand,
    PaymentConfirmed,
)
from billing.application.errors import (
    AccountNotFoundError,
    BillingApplicationError,
    FeeScheduleNotPublishedError,
    PaymentIntentNotFoundError,
)
from billing.application.initiate_payment import (
    InitiatePayment,
    InitiatePaymentCommand,
    PaymentInitiated,
)
from billing.application.link_student_account import (
    LinkStudentAccount,
    LinkStudentAccountCommand,
    StudentAccountLinked,
)
from billing.application.open_account_for_offer import (
    AccountOpened,
    OpenAccountForOffer,
    OpenAccountForOfferCommand,
)
from billing.application.read_account import AccountStatement, ReadAccount
from billing.application.reconcile_payment_intents import (
    ReconcilePaymentIntents,
    ReconciliationSwept,
)
from billing.application.record_payment import (
    PaymentRecorded,
    RecordPayment,
    RecordPaymentCommand,
)

__all__ = [
    "AccountNotFoundError",
    "AccountOpened",
    "AccountStatement",
    "ApplySessionFees",
    "BillingApplicationError",
    "ConfirmPayment",
    "ConfirmPaymentCommand",
    "FeeScheduleNotPublishedError",
    "InitiatePayment",
    "InitiatePaymentCommand",
    "LinkStudentAccount",
    "LinkStudentAccountCommand",
    "OpenAccountForOffer",
    "OpenAccountForOfferCommand",
    "PaymentConfirmed",
    "PaymentInitiated",
    "PaymentIntentNotFoundError",
    "PaymentRecorded",
    "ReadAccount",
    "ReconcilePaymentIntents",
    "ReconciliationSwept",
    "RecordPayment",
    "RecordPaymentCommand",
    "SessionFeesApplied",
    "StudentAccountLinked",
]
