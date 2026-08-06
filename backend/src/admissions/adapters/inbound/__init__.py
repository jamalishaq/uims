"""Admissions inbound adapters.

One event handler, and it is the only thing this context consumes from anybody. Admissions
asks Faculty & Department a question through a query port and tells Billing and Student
Profile two facts through a publisher; the single message that arrives *here* is Billing
saying the gating acceptance fee cleared.

It translates and does not decide. Whether the money arrived was settled in Billing before
the event was published; what clearing the fee unlocks — that a registrar may now matriculate
this applicant — is the domain's on this side, and deliberately not the same act.

The HTTP routes live in ``http/`` and are not re-exported here: they are mounted by the
composition root through the router module, not imported as objects.
"""

from admissions.adapters.inbound.acceptance_fee_paid_handler import (
    ACCEPTANCE_FEE_PAID,
    AcceptanceFeePaidHandler,
    AcceptanceFeePaidMessage,
)

__all__ = [
    "ACCEPTANCE_FEE_PAID",
    "AcceptanceFeePaidHandler",
    "AcceptanceFeePaidMessage",
]
