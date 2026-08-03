"""In-memory ``EventPublisherPort``: publishing means remembering.

Enough for the MVP and for tests to assert what a use case announced — and here the assertion
that matters is a *count*: ``AcceptanceFeePaid`` fires exactly once per applicant, which is
only checkable against something that keeps every event it was given, including the ones it
should never have been given twice.

Delivery to Admissions is a later concern. When it arrives it is a different adapter behind
this same port — Faculty & Department's ``InMemoryEventBus`` is exactly that, one port with a
remembering implementation and a delivering one — and no use case here changes.
"""

from billing.domain.events import DomainEvent
from billing.ports.event_publisher import EventPublisherPort


class InMemoryEventPublisher(EventPublisherPort):
    """Records every published event in the order it was published."""

    def __init__(self) -> None:
        self._published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self._published.append(event)

    @property
    def published(self) -> tuple[DomainEvent, ...]:
        """What has been published so far. A copy: callers cannot rewrite history."""
        return tuple(self._published)

    def clear(self) -> None:
        self._published.clear()
