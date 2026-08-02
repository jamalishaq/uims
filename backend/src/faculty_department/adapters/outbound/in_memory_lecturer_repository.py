"""Dict-backed ``LecturerRepositoryPort``."""

from faculty_department.adapters.outbound._store import InMemoryStore
from faculty_department.domain.lecturer import Lecturer
from faculty_department.ports.lecturer_repository import LecturerRepositoryPort


class InMemoryLecturerRepository(LecturerRepositoryPort):
    """Holds lecturers, and therefore their course assignments, in memory."""

    def __init__(self) -> None:
        self._store = InMemoryStore[Lecturer]("lecturer", lambda lecturer: lecturer.lecturer_id)

    def add(self, lecturer: Lecturer) -> None:
        self._store.add(lecturer)

    def save(self, lecturer: Lecturer) -> None:
        self._store.save(lecturer)

    def get(self, lecturer_id: str) -> Lecturer | None:
        return self._store.get(lecturer_id)

    def list_for_department(self, department_id: str) -> tuple[Lecturer, ...]:
        return tuple(
            lecturer for lecturer in self._store.all() if lecturer.department_id == department_id
        )
