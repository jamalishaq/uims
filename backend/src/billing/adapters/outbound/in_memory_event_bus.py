"""In-memory ``EventPublisherPort`` for Billing that actually delivers.

The successor :class:`InMemoryEventPublisher` promised — "Delivery to Admissions is a later
concern. When it arrives it is a different adapter behind this same port". This is that
adapter, and ``RecordPayment`` does not change, does not know it is being listened to, and
could not name a subscriber if it wanted to.

Thin on purpose: topics, serialisation and ordered delivery all live in ``src/event_bus.py``,
a flat module no context owns. This class exists to satisfy *this* context's port with *this*
context's event type. Admissions and Faculty & Department carry the same ten lines.

``bus`` is a constructor argument because the composition root needs **one** bus for the
process: Billing publishes ``AcceptanceFeePaid`` to Admissions and Admissions publishes
``OfferAccepted`` back. That the two contexts point at each other is fine and is not a
dependency — what crosses is a topic name and a mapping, and neither imports the other.

:class:`InMemoryEventPublisher` stays beside this rather than being replaced by it. It is the
recorder the tests that count publications drive, and counting is what proves
``AcceptanceFeePaid`` fires exactly once per applicant.
"""

from billing.domain.events import DomainEvent
from billing.ports.event_publisher import EventPublisherPort
from event_bus import EventBus, Subscriber


class InMemoryEventBus(EventPublisherPort):
    """Publishes by delivering to whoever subscribed on the shared bus."""

    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus if bus is not None else EventBus()

    def subscribe(self, event_name: str, subscriber: Subscriber) -> None:
        """Register ``subscriber`` for events published under ``event_name``."""
        self._bus.subscribe(event_name, subscriber)

    async def publish(self, event: DomainEvent) -> None:
        """Serialise ``event`` and hand it to every subscriber, in subscription order."""
        await self._bus.publish(event)

    @property
    def published(self) -> tuple[DomainEvent, ...]:
        """What has been published so far. A copy: callers cannot rewrite history."""
        return self._bus.published

    def subscribers_for(self, event_name: str) -> tuple[Subscriber, ...]:
        """Who is listening for one event. A copy, so the registry cannot be edited in place."""
        return self._bus.subscribers_for(event_name)

    def clear(self) -> None:
        """Forget what was published. Subscriptions survive — they are wiring, not history."""
        self._bus.clear()
