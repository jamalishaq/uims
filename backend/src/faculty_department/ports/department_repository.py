"""Outbound port for storing and retrieving departments."""

from abc import ABC, abstractmethod

from faculty_department.domain.department import Department


class DepartmentRepositoryPort(ABC):
    """Persistence for the ``Department`` aggregate."""

    @abstractmethod
    async def add(self, department: Department) -> None:
        """Store a new department.

        Raises:
            DuplicateAggregateError: the department id is already held.
        """

    @abstractmethod
    async def save(self, department: Department) -> None:
        """Persist changes to a department that is already stored.

        Raises:
            AggregateNotFoundError: the department id was never added.
        """

    @abstractmethod
    async def get(self, department_id: str) -> Department | None:
        """Return the department, or ``None`` if no such id is held."""

    @abstractmethod
    async def list_for_faculty(self, faculty_id: str) -> tuple[Department, ...]:
        """Every department under one faculty, in the order it was added."""
