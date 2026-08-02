"""Outbound port for announcing this context's domain events.

The port is deliberately ignorant of who listens. Faculty & Department states the fact;
which contexts react to it — Billing to ``SessionOpened``, Academic Records to
``GradeSubmitted`` — is not this context's business and never appears in this signature.
"""

from abc import ABC, abstractmethod

from faculty_department.domain.events import DomainEvent


class EventPublisherPort(ABC):
    """Publishes a domain event to whatever transport the adapter provides."""

    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """Announce that ``event`` happened."""
