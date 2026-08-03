"""In-memory ``EventPublisherPort``: publishing means remembering.

Enough for the MVP and for tests to assert what a use case announced. Delivery to other
contexts is a later concern — Phase 4.2 introduces the bus that carries ``GradeSubmitted``
to Academic Records, and it arrives as a different adapter behind this same port.
"""

from faculty_department.domain.events import DomainEvent
from faculty_department.ports.event_publisher import EventPublisherPort


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
