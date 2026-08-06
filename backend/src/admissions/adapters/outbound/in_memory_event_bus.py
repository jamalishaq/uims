"""In-memory ``EventPublisherPort`` for Admissions, backed by the shared bus.

Thin on purpose. Everything that makes a bus a bus — topics, serialisation, ordered
delivery — lives in ``src/event_bus.py``, a flat module no context owns; this class exists
to satisfy *this* context's port with *this* context's event type, so that the port stays
typed in Admissions' own vocabulary and the machinery is written once. Billing and Faculty &
Department carry the same ten lines for the same reason.

``bus`` is a constructor argument rather than something built here, because the composition
root needs **one** bus for the whole process: Admissions publishes ``OfferAccepted`` to
Billing and Billing publishes ``AcceptanceFeePaid`` back. Two buses would make that a pair
of monologues.
"""

from admissions.domain.events import DomainEvent
from admissions.ports.event_publisher import EventPublisherPort
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
