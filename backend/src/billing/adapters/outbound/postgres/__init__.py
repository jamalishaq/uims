"""Postgres outbound adapters for Billing.

The ledger, the schedules that price it and the intents that feed it. ``PaymentGatewayPort``
is not here and never will be: a gateway is a third party rather than storage, and the stub
beside it is replaced by an HTTP client rather than by a table.
"""

from billing.adapters.outbound.postgres._tables import SCHEMA, metadata
from billing.adapters.outbound.postgres.repositories import (
    PostgresAccountRepository,
    PostgresFeeScheduleRepository,
    PostgresPaymentIntentRepository,
)

__all__ = [
    "SCHEMA",
    "PostgresAccountRepository",
    "PostgresFeeScheduleRepository",
    "PostgresPaymentIntentRepository",
    "metadata",
]
