"""Dict-backed ``DepartmentRepositoryPort``."""

from faculty_department.adapters.outbound._store import InMemoryStore
from faculty_department.domain.department import Department
from faculty_department.ports.department_repository import DepartmentRepositoryPort


class InMemoryDepartmentRepository(DepartmentRepositoryPort):
    """Holds departments in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[Department](
            "department", lambda department: department.department_id
        )

    async def add(self, department: Department) -> None:
        self._store.add(department)

    async def save(self, department: Department) -> None:
        self._store.save(department)

    async def get(self, department_id: str) -> Department | None:
        return self._store.get(department_id)

    async def list_for_faculty(self, faculty_id: str) -> tuple[Department, ...]:
        return tuple(
            department for department in self._store.all() if department.faculty_id == faculty_id
        )
