"""Billing outbound adapters.

In-memory implementations of the repository and publisher ports, plus a scriptable stand-in
for the payment gateway — good enough to run the whole context and its test suite without a
database or a network. Phase 6 adds Postgres adapters alongside them; nothing above this
package should have to change when it does.

This is the context where that swap has the most to prove. The ledger's invariants are
enforced on the aggregate — a duplicate gateway reference is recognised in memory, not by a
constraint — and CLAUDE.md section 4 is explicit that when the database *also* catches one, a
unique-constraint violation is a permanent failure translated immediately into the domain's
idempotency no-op rather than retried. The in-memory adapters cannot exercise that path, which
is precisely why the invariant does not live in them.

The real gateway client is still to come, and :class:`StubPaymentGateway` is not a stand-in
for its *behaviour* — only for its answers. What Phase 6 adds behind
``PaymentGatewayPort`` is the part that cannot be faked: explicit timeouts, retries with
exponential backoff and jitter on transient errors only, a circuit breaker, and third-party
exceptions translated at this boundary so that none of them reaches the application layer.
The one thing the stub does model is the *shape* of that failure —
``PaymentGatewayUnavailableError`` — because reconciliation's handling of an unanswered
question is a rule, and rules get tests.
"""

from billing.adapters.outbound.in_memory_account_repository import InMemoryAccountRepository
from billing.adapters.outbound.in_memory_event_bus import InMemoryEventBus
from billing.adapters.outbound.in_memory_event_publisher import InMemoryEventPublisher
from billing.adapters.outbound.in_memory_fee_schedule_repository import (
    InMemoryFeeScheduleRepository,
)
from billing.adapters.outbound.in_memory_payment_intent_repository import (
    InMemoryPaymentIntentRepository,
)
from billing.adapters.outbound.stub_payment_gateway import StubPaymentGateway

__all__ = [
    "InMemoryAccountRepository",
    "InMemoryEventBus",
    "InMemoryEventPublisher",
    "InMemoryFeeScheduleRepository",
    "InMemoryPaymentIntentRepository",
    "StubPaymentGateway",
]
