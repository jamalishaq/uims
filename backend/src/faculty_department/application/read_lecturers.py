"""Reading staff: one lecturer, or a department's.

``list_for_department`` has been on ``LecturerRepositoryPort`` since the first phase with no
caller. This is it — and it is the staff half of what a departmental view needs, beside
``ListDepartmentPrograms``.

Both are straight reads. ``find`` answers ``None`` rather than raising, in the manner of
``ReadAccount.find``: absence is a normal answer to a question about an identifier a caller
was handed by somebody else, and the route turns it into a 404 without catching anything.
"""

from dataclasses import dataclass

from faculty_department.domain.lecturer import Lecturer
from faculty_department.ports.lecturer_repository import LecturerRepositoryPort


@dataclass(frozen=True)
class ListDepartmentLecturersCommand:
    """Whose staff to list."""

    department_id: str


class ReadLecturer:
    """One member of staff, their profile and what they teach."""

    def __init__(self, lecturers: LecturerRepositoryPort) -> None:
        self._lecturers = lecturers

    async def find(self, lecturer_id: str) -> Lecturer | None:
        """The lecturer, or ``None`` if nobody has that id."""
        return await self._lecturers.get(lecturer_id)


class ListDepartmentLecturers:
    """Everyone teaching in a department."""

    def __init__(self, lecturers: LecturerRepositoryPort) -> None:
        self._lecturers = lecturers

    async def execute(self, command: ListDepartmentLecturersCommand) -> tuple[Lecturer, ...]:
        """The department's staff, whatever they are or are not teaching this session.

        A department nobody has is an empty list rather than a 404, for
        ``ListDepartmentPrograms``' reason: this use case raises nothing, and the repository
        cannot tell an unknown department from one with no staff yet.
        """
        return await self._lecturers.list_for_department(command.department_id)
