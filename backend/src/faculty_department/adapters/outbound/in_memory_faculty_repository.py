"""Dict-backed ``FacultyRepositoryPort``."""

from faculty_department.adapters.outbound._store import InMemoryStore
from faculty_department.domain.faculty import Faculty
from faculty_department.ports.faculty_repository import FacultyRepositoryPort


class InMemoryFacultyRepository(FacultyRepositoryPort):
    """Holds faculties in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[Faculty]("faculty", lambda faculty: faculty.faculty_id)

    async def add(self, faculty: Faculty) -> None:
        self._store.add(faculty)

    async def save(self, faculty: Faculty) -> None:
        self._store.save(faculty)

    async def get(self, faculty_id: str) -> Faculty | None:
        return self._store.get(faculty_id)

    async def list_all(self) -> tuple[Faculty, ...]:
        return self._store.all()
