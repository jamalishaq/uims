"""Dict-backed ``SessionRepositoryPort``."""

from faculty_department.adapters.outbound._store import InMemoryStore
from faculty_department.domain.session import Session
from faculty_department.ports.session_repository import SessionRepositoryPort


class InMemorySessionRepository(SessionRepositoryPort):
    """Holds sessions, and therefore their semesters, in memory."""

    def __init__(self) -> None:
        self._store = InMemoryStore[Session]("session", lambda session: session.session_id)

    def add(self, session: Session) -> None:
        self._store.add(session)

    def save(self, session: Session) -> None:
        self._store.save(session)

    def get(self, session_id: str) -> Session | None:
        return self._store.get(session_id)

    def list_all(self) -> tuple[Session, ...]:
        return self._store.all()
