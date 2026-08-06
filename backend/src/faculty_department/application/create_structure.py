"""Creating the academic structure: faculties, departments and programs.

Three write paths for the three levels of the hierarchy, and until they existed none of them
could be created except by writing rows into Postgres by hand. That was the largest gap in
this context: it owns the most-queried data in the system — Admissions asks whether a program
is admitting, Student Profile asks which department is behind it — and had no way to be given
any.

**Each level checks that the one above it exists.** A department naming a faculty nobody has,
or a program naming a missing department, would be a dangling reference that surfaces much
later and somewhere else: ``ReadProgramPlacement`` answers ``None`` when the join fails, so
the eventual symptom is an applicant being told their program does not exist. Checking here
turns that into a 404 at the moment somebody typed the wrong id.

That check is also what finally gives ``FacultyRepositoryPort`` a caller. ``src/main.py``
recorded its absence as a finding rather than an oversight — "no use case in the system reads
a faculty" — and :class:`CreateDepartment` is the use case that does.

**Programs are created not admitting.** ``Program.create`` leaves the flag false and
:class:`SetProgramAdmissions` is the only thing that moves it, so a program cannot start
taking applications as a side effect of being described. Opening admissions is a decision
somebody makes on a program that already exists.
"""

from dataclasses import dataclass

from faculty_department.application.errors import (
    DepartmentNotFoundError,
    FacultyNotFoundError,
    ProgramNotFoundError,
)
from faculty_department.domain.department import Department
from faculty_department.domain.faculty import Faculty
from faculty_department.domain.program import Program
from faculty_department.ports.department_repository import DepartmentRepositoryPort
from faculty_department.ports.faculty_repository import FacultyRepositoryPort
from faculty_department.ports.program_repository import ProgramRepositoryPort


@dataclass(frozen=True)
class CreateFacultyCommand:
    """A faculty, e.g. the Faculty of Science."""

    faculty_id: str
    name: str
    code: str


@dataclass(frozen=True)
class CreateDepartmentCommand:
    """A department inside a faculty.

    ``code`` is this context's alphabetic code (``CSC``). The four numeric digits a matric
    number carries are Student Profile's translation of it and are configured there, which is
    why nothing here asks for them.
    """

    department_id: str
    faculty_id: str
    name: str
    code: str


@dataclass(frozen=True)
class CreateProgramCommand:
    """A program offered by a department. Created *not* admitting."""

    program_id: str
    department_id: str
    name: str
    code: str


@dataclass(frozen=True)
class SetProgramAdmissionsCommand:
    """Open or close a program's admissions window.

    Session-less, as this context holds it. Admissions asks per session and reconciles the two
    in its own adapter — a program is admitting *for a session* only when this flag is set and
    that session is open — so this is one half of that answer rather than the whole of it.
    """

    program_id: str
    is_admitting: bool


class CreateFaculty:
    """Add a faculty to the structure."""

    def __init__(self, faculties: FacultyRepositoryPort) -> None:
        self._faculties = faculties

    async def execute(self, command: CreateFacultyCommand) -> Faculty:
        """Create and store the faculty.

        Raises:
            DuplicateAggregateError: a faculty already has that id.
            MissingIdentifierError: an identifier, name or code is blank.
        """
        faculty = Faculty(faculty_id=command.faculty_id, name=command.name, code=command.code)
        await self._faculties.add(faculty)
        return faculty


class CreateDepartment:
    """Add a department to a faculty that exists."""

    def __init__(
        self,
        departments: DepartmentRepositoryPort,
        faculties: FacultyRepositoryPort,
    ) -> None:
        self._departments = departments
        self._faculties = faculties

    async def execute(self, command: CreateDepartmentCommand) -> Department:
        """Check the faculty, then create and store the department.

        Raises:
            FacultyNotFoundError: no faculty is stored under that id.
            DuplicateAggregateError: a department already has that id.
            MissingIdentifierError: an identifier, name or code is blank.
        """
        if await self._faculties.get(command.faculty_id) is None:
            raise FacultyNotFoundError(f"no faculty stored with id {command.faculty_id!r}")

        department = Department(
            department_id=command.department_id,
            faculty_id=command.faculty_id,
            name=command.name,
            code=command.code,
        )
        await self._departments.add(department)
        return department


class CreateProgram:
    """Add a program to a department that exists."""

    def __init__(
        self,
        programs: ProgramRepositoryPort,
        departments: DepartmentRepositoryPort,
    ) -> None:
        self._programs = programs
        self._departments = departments

    async def execute(self, command: CreateProgramCommand) -> Program:
        """Check the department, then create and store the program, not admitting.

        Raises:
            DepartmentNotFoundError: no department is stored under that id.
            DuplicateAggregateError: a program already has that id.
            MissingIdentifierError: an identifier, name or code is blank.
        """
        if await self._departments.get(command.department_id) is None:
            raise DepartmentNotFoundError(f"no department stored with id {command.department_id!r}")

        program = Program.create(
            program_id=command.program_id,
            department_id=command.department_id,
            name=command.name,
            code=command.code,
        )
        await self._programs.add(program)
        return program


class SetProgramAdmissions:
    """Open or close a program's admissions window."""

    def __init__(self, programs: ProgramRepositoryPort) -> None:
        self._programs = programs

    async def execute(self, command: SetProgramAdmissionsCommand) -> Program:
        """Move the flag and store the program.

        Idempotent: opening an already-open program is a no-op rather than an error, because
        the aggregate's methods are assignments rather than transitions and the caller's
        intent — "this program should be admitting" — is satisfied either way.

        Raises:
            ProgramNotFoundError: no program is stored under that id.
        """
        program = await self._programs.get(command.program_id)
        if program is None:
            raise ProgramNotFoundError(f"no program stored with id {command.program_id!r}")

        if command.is_admitting:
            program.open_admissions()
        else:
            program.close_admissions()
        await self._programs.save(program)
        return program
