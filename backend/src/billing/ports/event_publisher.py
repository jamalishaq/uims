"""Outbound port for announcing this context's domain events.

The port is deliberately ignorant of who listens. Billing states that an acceptance fee was
paid; that Admissions reacts by setting a flag which gates matriculation is not this
context's business and never appears in this signature. Billing does not know matriculation
exists.

The same port shape Faculty & Department carries, and for the same reason: the publisher and
the subscriber are introduced to each other in a composition root that imports both, and
neither imports the other.
"""

from abc import ABC, abstractmethod

from billing.domain.events import DomainEvent


class EventPublisherPort(ABC):
    """Publishes a domain event to whatever transport the adapter provides."""

    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """Announce that ``event`` happened."""
