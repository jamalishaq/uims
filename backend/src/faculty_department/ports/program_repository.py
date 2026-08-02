"""Outbound port for storing and retrieving programs."""

from abc import ABC, abstractmethod

from faculty_department.domain.program import Program


class ProgramRepositoryPort(ABC):
    """Persistence for the ``Program`` aggregate."""

    @abstractmethod
    def add(self, program: Program) -> None:
        """Store a new program.

        Raises:
            DuplicateAggregateError: the program id is already held.
        """

    @abstractmethod
    def save(self, program: Program) -> None:
        """Persist changes to a program that is already stored.

        Raises:
            AggregateNotFoundError: the program id was never added.
        """

    @abstractmethod
    def get(self, program_id: str) -> Program | None:
        """Return the program, or ``None`` if no such id is held."""

    @abstractmethod
    def list_for_department(self, department_id: str) -> tuple[Program, ...]:
        """Every program offered by one department, in the order it was added."""
