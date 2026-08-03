"""Faculty & Department's five repository ports, against Postgres.

Each class is the port's method list and nothing else: the transaction discipline, the
identity map, the retries and the error translation all sit in
:class:`~faculty_department.adapters.outbound.postgres._repository.PostgresRepository`, so
what is left here is which table, which key, and how a row becomes an aggregate.

Named ``<Storage><Aggregate>Repository`` per CLAUDE.md section 2, beside the
``InMemory<Aggregate>Repository`` they stand in for. Both satisfy the same port and the same
tests, which is the claim the whole phase rests on.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Row, Table
from sqlalchemy.ext.asyncio import AsyncEngine

from faculty_department.adapters.outbound.postgres import _mapping as m
from faculty_department.adapters.outbound.postgres import _tables as t
from faculty_department.adapters.outbound.postgres._repository import PostgresRepository
from faculty_department.domain.department import Department
from faculty_department.domain.faculty import Faculty
from faculty_department.domain.lecturer import Lecturer
from faculty_department.domain.program import Program
from faculty_department.domain.session import Session
from faculty_department.ports.department_repository import DepartmentRepositoryPort
from faculty_department.ports.faculty_repository import FacultyRepositoryPort
from faculty_department.ports.lecturer_repository import LecturerRepositoryPort
from faculty_department.ports.program_repository import ProgramRepositoryPort
from faculty_department.ports.session_repository import SessionRepositoryPort


class PostgresFacultyRepository(PostgresRepository[Faculty], FacultyRepositoryPort):
    """Holds faculties in Postgres."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine, label="faculty", table=t.faculties, key=("faculty_id",))

    def identity_of(self, aggregate: Faculty) -> tuple[str]:
        return (aggregate.faculty_id,)

    def row_of(self, aggregate: Faculty) -> dict[str, Any]:
        return m.faculty_row(aggregate)

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> Faculty:
        return m.to_faculty(row)

    async def add(self, faculty: Faculty) -> None:
        await self._add(faculty)

    async def save(self, faculty: Faculty) -> None:
        await self._save(faculty)

    async def get(self, faculty_id: str) -> Faculty | None:
        return await self._get(faculty_id)

    async def list_all(self) -> tuple[Faculty, ...]:
        return await self._list()


class PostgresDepartmentRepository(PostgresRepository[Department], DepartmentRepositoryPort):
    """Holds departments in Postgres."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine, label="department", table=t.departments, key=("department_id",))

    def identity_of(self, aggregate: Department) -> tuple[str]:
        return (aggregate.department_id,)

    def row_of(self, aggregate: Department) -> dict[str, Any]:
        return m.department_row(aggregate)

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> Department:
        return m.to_department(row)

    async def add(self, department: Department) -> None:
        await self._add(department)

    async def save(self, department: Department) -> None:
        await self._save(department)

    async def get(self, department_id: str) -> Department | None:
        return await self._get(department_id)

    async def list_for_faculty(self, faculty_id: str) -> tuple[Department, ...]:
        return await self._list(t.departments.c.faculty_id == faculty_id)


class PostgresProgramRepository(PostgresRepository[Program], ProgramRepositoryPort):
    """Holds programs in Postgres."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine, label="program", table=t.programs, key=("program_id",))

    def identity_of(self, aggregate: Program) -> tuple[str]:
        return (aggregate.program_id,)

    def row_of(self, aggregate: Program) -> dict[str, Any]:
        return m.program_row(aggregate)

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> Program:
        return m.to_program(row)

    async def add(self, program: Program) -> None:
        await self._add(program)

    async def save(self, program: Program) -> None:
        await self._save(program)

    async def get(self, program_id: str) -> Program | None:
        return await self._get(program_id)

    async def list_for_department(self, department_id: str) -> tuple[Program, ...]:
        return await self._list(t.programs.c.department_id == department_id)


class PostgresLecturerRepository(PostgresRepository[Lecturer], LecturerRepositoryPort):
    """Holds lecturers, and therefore their course assignments, in Postgres.

    The assignments are part of the aggregate, so they are written and read with it — "there
    is no separate assignment repository to fall out of step", as the port puts it.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine, label="lecturer", table=t.lecturers, key=("lecturer_id",))

    @property
    def child_tables(self) -> Sequence[tuple[Table, Sequence[str]]]:
        return ((t.lecturer_assignments, ("lecturer_id",)),)

    def identity_of(self, aggregate: Lecturer) -> tuple[str]:
        return (aggregate.lecturer_id,)

    def row_of(self, aggregate: Lecturer) -> dict[str, Any]:
        return m.lecturer_row(aggregate)

    def child_rows_of(self, aggregate: Lecturer) -> Mapping[Table, Sequence[dict[str, Any]]]:
        return {t.lecturer_assignments: m.assignment_rows(aggregate)}

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> Lecturer:
        return m.to_lecturer(row, m.children_of(children, t.lecturer_assignments))

    async def add(self, lecturer: Lecturer) -> None:
        await self._add(lecturer)

    async def save(self, lecturer: Lecturer) -> None:
        await self._save(lecturer)

    async def get(self, lecturer_id: str) -> Lecturer | None:
        return await self._get(lecturer_id)

    async def list_for_department(self, department_id: str) -> tuple[Lecturer, ...]:
        return await self._list(t.lecturers.c.department_id == department_id)


class PostgresSessionRepository(PostgresRepository[Session], SessionRepositoryPort):
    """Holds sessions, and therefore their semesters, in Postgres.

    The only repository here whose aggregate carries state no constructor can express, which
    is why ``Session.restore`` exists and why nothing else in this context needed one.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine, label="session", table=t.sessions, key=("session_id",))

    @property
    def child_tables(self) -> Sequence[tuple[Table, Sequence[str]]]:
        return ((t.semesters, ("session_id",)),)

    def identity_of(self, aggregate: Session) -> tuple[str]:
        return (aggregate.session_id,)

    def row_of(self, aggregate: Session) -> dict[str, Any]:
        return m.session_row(aggregate)

    def child_rows_of(self, aggregate: Session) -> Mapping[Table, Sequence[dict[str, Any]]]:
        return {t.semesters: m.semester_rows(aggregate)}

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> Session:
        return m.to_session(row, m.children_of(children, t.semesters))

    async def add(self, session: Session) -> None:
        await self._add(session)

    async def save(self, session: Session) -> None:
        await self._save(session)

    async def get(self, session_id: str) -> Session | None:
        return await self._get(session_id)

    async def list_all(self) -> tuple[Session, ...]:
        return await self._list()
