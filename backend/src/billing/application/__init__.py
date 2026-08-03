"""Billing application layer.

Five use cases, and the shape of the set says what this context is. Two are driven by events
from elsewhere and raise charges (:class:`OpenAccountForOffer`, :class:`ApplySessionFees`);
one is driven by money arriving and is the only way money ever gets onto a ledger
(:class:`RecordPayment`); one is an administrative act nothing publishes yet
(:class:`LinkStudentAccount`); one only reads (:class:`ReadAccount`).

That there is no sixth is the point. No "recompute balance" — a balance is derived from the
charges and payments on read, so there is no stored figure to fall out of step. No "settle
charge", because charges settle by being paid rather than by being marked. No "clear student
for registration", because that judgement is a rule behind ``FinancialClearancePort`` and not
a thing anybody does. And no refunds: a deferred admin use case (CLAUDE.md section 3), which
when it arrives will be entries on the ledger rather than a subtraction.

Orchestration only. Every rule these use cases appear to apply belongs to the domain: which
charge a payment goes to, whether a gateway reference has been seen, whether an overpayment is
allowed. What is decided here is what a use case is allowed to decide — that an unpriced
account is skipped rather than failed, that a session with no schedule at all stops the batch,
and that money for a party with no ledger is refused rather than made to fit.
"""

from billing.application.apply_session_fees import ApplySessionFees, SessionFeesApplied
from billing.application.errors import (
    AccountNotFoundError,
    BillingApplicationError,
    FeeScheduleNotPublishedError,
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
    "FeeScheduleNotPublishedError",
    "LinkStudentAccount",
    "LinkStudentAccountCommand",
    "OpenAccountForOffer",
    "OpenAccountForOfferCommand",
    "PaymentRecorded",
    "ReadAccount",
    "RecordPayment",
    "RecordPaymentCommand",
    "SessionFeesApplied",
    "StudentAccountLinked",
]
