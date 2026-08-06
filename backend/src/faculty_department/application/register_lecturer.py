"""Add a lecturer to a department.

The other half of ``SubmitGrade``'s authorization. That use case asks a stored ``Lecturer``
whether they teach the course they are submitting a grade for — authorization against data
this context already owns (CLAUDE.md section 3) — and until now there was no way to store one.

**Course assignments are not set here.** A lecturer is created teaching nothing, and
``assign_to_course`` moves that separately. Bundling the two would make "who teaches what" a
property of hiring somebody, when it is a decision taken again every session.
"""

from dataclasses import dataclass

from faculty_department.application.errors import DepartmentNotFoundError
from faculty_department.domain.lecturer import Lecturer
from faculty_department.ports.department_repository import DepartmentRepositoryPort
from faculty_department.ports.lecturer_repository import LecturerRepositoryPort


@dataclass(frozen=True)
class RegisterLecturerCommand:
    """A lecturer and the department they belong to.

    The staff record — rank, employment status, qualifications — is **not set here**. A
    lecturer is created as a name in a department, and ``AmendLecturerProfile`` fills the rest
    in. That is not squeamishness about a longer command: a lecturer is often created from a
    list of names before anybody has their file, and a create route that demanded a rank would
    be a create route somebody works around by picking one.
    """

    lecturer_id: str
    department_id: str
    full_name: str


class RegisterLecturer:
    """Add a lecturer to a department that exists."""

    def __init__(
        self,
        lecturers: LecturerRepositoryPort,
        departments: DepartmentRepositoryPort,
    ) -> None:
        self._lecturers = lecturers
        self._departments = departments

    async def execute(self, command: RegisterLecturerCommand) -> Lecturer:
        """Check the department, then create and store the lecturer.

        Raises:
            DepartmentNotFoundError: no department is stored under that id. A lecturer in a
                department nobody has could still submit grades — ``SubmitGrade`` reads the
                assignment, not the department — so the dangling reference would be invisible
                until somebody tried to list a department's staff.
            DuplicateAggregateError: a lecturer already has that id.
            MissingIdentifierError: an identifier or the name is blank.
        """
        if await self._departments.get(command.department_id) is None:
            raise DepartmentNotFoundError(f"no department stored with id {command.department_id!r}")

        lecturer = Lecturer(
            lecturer_id=command.lecturer_id,
            department_id=command.department_id,
            full_name=command.full_name,
        )
        await self._lecturers.add(lecturer)
        return lecturer
