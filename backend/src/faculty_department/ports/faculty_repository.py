"""Outbound port for storing and retrieving faculties."""

from abc import ABC, abstractmethod

from faculty_department.domain.faculty import Faculty


class FacultyRepositoryPort(ABC):
    """Persistence for the ``Faculty`` aggregate."""

    @abstractmethod
    def add(self, faculty: Faculty) -> None:
        """Store a new faculty.

        Raises:
            DuplicateAggregateError: the faculty id is already held.
        """

    @abstractmethod
    def save(self, faculty: Faculty) -> None:
        """Persist changes to a faculty that is already stored.

        Raises:
            AggregateNotFoundError: the faculty id was never added.
        """

    @abstractmethod
    def get(self, faculty_id: str) -> Faculty | None:
        """Return the faculty, or ``None`` if no such id is held."""

    @abstractmethod
    def list_all(self) -> tuple[Faculty, ...]:
        """Every stored faculty, in the order it was added."""
