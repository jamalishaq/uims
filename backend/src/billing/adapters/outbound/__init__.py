"""Billing outbound adapters.

In-memory implementations of the three ports, good enough to run the whole context and its
test suite without a database. Phase 6 adds Postgres adapters alongside them; nothing above
this package should have to change when it does.

This is the context where that swap has the most to prove. The ledger's invariants are
enforced on the aggregate — a duplicate gateway reference is recognised in memory, not by a
constraint — and CLAUDE.md section 4 is explicit that when the database *also* catches one, a
unique-constraint violation is a permanent failure translated immediately into the domain's
idempotency no-op rather than retried. The in-memory adapters cannot exercise that path, which
is precisely why the invariant does not live in them.

There is no gateway client here. Phase 5.3 adds ``PaymentGatewayPort`` and the client behind
it, with retries, timeouts and a circuit breaker; this phase records payments that somebody
else has already confirmed.
"""

from billing.adapters.outbound.in_memory_account_repository import InMemoryAccountRepository
from billing.adapters.outbound.in_memory_event_publisher import InMemoryEventPublisher
from billing.adapters.outbound.in_memory_fee_schedule_repository import (
    InMemoryFeeScheduleRepository,
)

__all__ = [
    "InMemoryAccountRepository",
    "InMemoryEventPublisher",
    "InMemoryFeeScheduleRepository",
]
