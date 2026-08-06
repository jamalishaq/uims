"""Outbound port for announcing this context's domain events.

The port is deliberately ignorant of who listens. Admissions states that an offer was
accepted; that Billing reacts by opening a ledger and raising two admission charges is not
this context's business and never appears in this signature. Admissions does not know
Billing exists.

The same port shape Faculty & Department and Billing carry, and for the same reason: the
publisher and the subscriber are introduced to each other in a composition root that imports
both, and neither imports the other.
"""

from abc import ABC, abstractmethod

from admissions.domain.events import DomainEvent


class EventPublisherPort(ABC):
    """Publishes a domain event to whatever transport the adapter provides."""

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Announce that ``event`` happened."""
