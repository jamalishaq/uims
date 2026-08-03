"""Dict-backed ``PaymentIntentRepositoryPort``, keyed by the gateway's reference.

The plainest adapter in this context: one store, no alias index, because an intent answers to
exactly one name and it is the gateway's own. ``InMemoryAccountRepository`` next door has to
resolve two ids for one ledger; here the identifier arrived from outside and never changes.

:meth:`all_initiated` filters in Python, which is what an in-memory store can do. The Postgres
adapter of Phase 6 will make it a ``WHERE status = 'initiated'`` over an index — the same
query, and deliberately still not a query about *time*: which of the open intents have gone
quiet long enough to chase is Billing's judgement, and it stays in the use case rather than
being pushed down here where a swap could quietly change it.
"""

from billing.adapters.outbound._store import InMemoryStore
from billing.domain.payment_intent import PaymentIntent, PaymentIntentStatus
from billing.ports.payment_intent_repository import PaymentIntentRepositoryPort


class InMemoryPaymentIntentRepository(PaymentIntentRepositoryPort):
    """Holds payment intents in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[PaymentIntent](
            "payment intent", lambda intent: intent.reference
        )

    def add(self, intent: PaymentIntent) -> None:
        self._store.add(intent)

    def save(self, intent: PaymentIntent) -> None:
        self._store.save(intent)

    def get(self, reference: str) -> PaymentIntent | None:
        return self._store.get(reference)

    def all_initiated(self) -> tuple[PaymentIntent, ...]:
        """Every intent the gateway has not yet answered about, in the order opened."""
        return tuple(
            intent for intent in self._store.all() if intent.status is PaymentIntentStatus.INITIATED
        )
