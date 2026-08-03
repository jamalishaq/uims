"""Billing ports layer.

The interfaces the outside world plugs into: persistence for the ``Account`` aggregate and
for this context's own session-scoped policy — the fee schedules — plus the publisher that
announces ``AcceptanceFeePaid``.

**There is no query port here, and that is the design.** Billing makes no synchronous request
of any other context. Everything it needs arrives as a past-tense fact it consumes:
``OfferAccepted`` brings a party and their program, ``SessionOpened`` brings a session. The
program and level a fee is keyed by are held on the account rather than fetched, which is
also what keeps a batch over every account in the university from being a query per account.

**And no ``PaymentGatewayPort``.** That arrives in Phase 5.3 alongside ``PaymentIntent`` and
reconciliation, and it is the security-sensitive path CLAUDE.md section 4 requires human
review of. Nothing in this phase talks to a gateway; ``RecordPayment`` takes a reference, an
amount and a timestamp from whoever calls it, which is what makes it gateway-agnostic.

The port Enrollment reaches this context through — ``FinancialClearancePort`` — is declared
over *there*, in Enrollment's own language, and the adapter answering it is Phase 5.2's. That
is the anti-corruption layer working as intended: the consuming context owns the interface.
"""

from billing.ports.account_repository import AccountRepositoryPort
from billing.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    RepositoryError,
)
from billing.ports.event_publisher import EventPublisherPort
from billing.ports.fee_schedule_repository import FeeScheduleRepositoryPort

__all__ = [
    "AccountRepositoryPort",
    "AggregateNotFoundError",
    "DuplicateAggregateError",
    "EventPublisherPort",
    "FeeScheduleRepositoryPort",
    "RepositoryError",
]
