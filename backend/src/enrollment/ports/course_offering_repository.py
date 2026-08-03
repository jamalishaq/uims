"""Outbound port for storing and retrieving course offerings."""

from abc import ABC, abstractmethod

from enrollment.domain.course_offering import CourseOffering
from enrollment.domain.values import Term


class CourseOfferingRepositoryPort(ABC):
    """Persistence for the ``CourseOffering`` aggregate.

    Keyed by ``(course_id, term)``, which is the offering's identity: the same course run
    again next semester is a different offering with its own seats, and a registration
    always names both.
    """

    @abstractmethod
    async def add(self, offering: CourseOffering) -> None:
        """Open a course for registration this term.

        Raises:
            DuplicateAggregateError: the course is already offered this term.
        """

    @abstractmethod
    async def save(self, offering: CourseOffering) -> None:
        """Persist a claimed seat.

        Raises:
            AggregateNotFoundError: the course was never offered this term.
        """

    @abstractmethod
    async def get(self, course_id: str, term: Term) -> CourseOffering | None:
        """Return the offering, or ``None`` if the course is not being run this term."""
