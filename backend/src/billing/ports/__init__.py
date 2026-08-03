"""Billing ports layer.

The interfaces the outside world plugs into: persistence for the ``Account`` and
``PaymentIntent`` aggregates and for this context's own session-scoped policy — the fee
schedules — the publisher that announces ``AcceptanceFeePaid``, and one read against the
payment gateway.

**There is still no query port into another context, and that is the design.** Billing makes
no synchronous request of any of the other six. Everything it needs from them arrives as a
past-tense fact it consumes: ``OfferAccepted`` brings a party and their program,
``SessionOpened`` brings a session. The program and level a fee is keyed by are held on the
account rather than fetched, which is also what keeps a batch over every account in the
university from being a query per account.

**``PaymentGatewayPort`` is not a counter-example to that.** A payment gateway is a third
party outside this system, not one of the seven bounded contexts, and asking it what became of
a reference acquires no dependency on anybody's domain model — the answer comes back as
:class:`~billing.domain.gateway.GatewayVerification`, which is Billing's own type. It is the
single named exemption in ``tests/billing/test_port_types_are_billing_owned.py``, by exact
name rather than by pattern, so that the next port with "gateway" in it still has to argue its
case. It exists because CLAUDE.md section 3 requires reconciliation to ask before writing an
intent off, and it is the security-sensitive path section 4 requires human review of.

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
from billing.ports.payment_gateway import (
    PaymentGatewayError,
    PaymentGatewayPort,
    PaymentGatewayUnavailableError,
)
from billing.ports.payment_intent_repository import PaymentIntentRepositoryPort

__all__ = [
    "AccountRepositoryPort",
    "AggregateNotFoundError",
    "DuplicateAggregateError",
    "EventPublisherPort",
    "FeeScheduleRepositoryPort",
    "PaymentGatewayError",
    "PaymentGatewayPort",
    "PaymentGatewayUnavailableError",
    "PaymentIntentRepositoryPort",
    "RepositoryError",
]
