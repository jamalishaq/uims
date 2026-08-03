"""Outbound port for storing and retrieving academic sessions."""

from abc import ABC, abstractmethod

from faculty_department.domain.session import Session


class SessionRepositoryPort(ABC):
    """Persistence for the ``Session`` aggregate, its semesters included."""

    @abstractmethod
    async def add(self, session: Session) -> None:
        """Store a new session.

        Raises:
            DuplicateAggregateError: the session id is already held.
        """

    @abstractmethod
    async def save(self, session: Session) -> None:
        """Persist changes to a session that is already stored — an open or close, say.

        Raises:
            AggregateNotFoundError: the session id was never added.
        """

    @abstractmethod
    async def get(self, session_id: str) -> Session | None:
        """Return the session, or ``None`` if no such id is held."""

    @abstractmethod
    async def list_all(self) -> tuple[Session, ...]:
        """Every stored session, in the order it was added."""
