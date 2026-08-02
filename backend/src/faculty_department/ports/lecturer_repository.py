"""Outbound port for storing and retrieving lecturers and their course assignments."""

from abc import ABC, abstractmethod

from faculty_department.domain.lecturer import Lecturer


class LecturerRepositoryPort(ABC):
    """Persistence for the ``Lecturer`` aggregate, assignments included.

    A lecturer's course assignments are part of the aggregate, so they are written and
    read with it: there is no separate assignment repository to fall out of step.
    """

    @abstractmethod
    def add(self, lecturer: Lecturer) -> None:
        """Store a new lecturer.

        Raises:
            DuplicateAggregateError: the lecturer id is already held.
        """

    @abstractmethod
    def save(self, lecturer: Lecturer) -> None:
        """Persist changes to a lecturer that is already stored.

        Raises:
            AggregateNotFoundError: the lecturer id was never added.
        """

    @abstractmethod
    def get(self, lecturer_id: str) -> Lecturer | None:
        """Return the lecturer, or ``None`` if no such id is held."""

    @abstractmethod
    def list_for_department(self, department_id: str) -> tuple[Lecturer, ...]:
        """Every lecturer in one department, in the order it was added."""
