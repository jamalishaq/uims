"""Dict-backed ``ProgramRepositoryPort``."""

from faculty_department.adapters.outbound._store import InMemoryStore
from faculty_department.domain.program import Program
from faculty_department.ports.program_repository import ProgramRepositoryPort


class InMemoryProgramRepository(ProgramRepositoryPort):
    """Holds programs in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[Program]("program", lambda program: program.program_id)

    def add(self, program: Program) -> None:
        self._store.add(program)

    def save(self, program: Program) -> None:
        self._store.save(program)

    def get(self, program_id: str) -> Program | None:
        return self._store.get(program_id)

    def list_for_department(self, department_id: str) -> tuple[Program, ...]:
        return tuple(
            program for program in self._store.all() if program.department_id == department_id
        )
