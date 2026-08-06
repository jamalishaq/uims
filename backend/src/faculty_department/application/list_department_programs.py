"""Every program a department offers — the inverse of the placement read.

``ReadProgramPlacement`` answers "which department is behind this program?", and that
direction has existed since the cross-context adapters needed it. This is the other one, and
it is what a departmental view is built on: a registrar knows their department and needs the
programs, not the other way round.

**It is also how a caller relates an applicant to a department without any context learning
about the other.** An ``Applicant`` carries programs and never a department; ``Program``
carries a department and never an applicant. A client that wants "the applicants for my
department" reads this list and then asks Admissions per program — two calls, no new
cross-context dependency, and Admissions is spared a notion of departments it has no other
reason to hold.

A department nobody has is an empty list rather than a 404, in the manner of Course Catalog's
``ListDepartmentCourses``: this use case raises nothing, and the repository cannot tell an
unknown department from one that offers nothing yet.
"""

from dataclasses import dataclass

from faculty_department.domain.program import Program
from faculty_department.ports.program_repository import ProgramRepositoryPort


@dataclass(frozen=True)
class ListDepartmentProgramsCommand:
    """Which department's programs to list."""

    department_id: str


class ListDepartmentPrograms:
    """List a department's programs."""

    def __init__(self, programs: ProgramRepositoryPort) -> None:
        self._programs = programs

    async def execute(self, command: ListDepartmentProgramsCommand) -> tuple[Program, ...]:
        """Every program the department offers, admitting or not.

        Closed programs are included deliberately. A registrar's dashboard has to show a
        program that is not taking applications this session — that is a fact about it, not a
        reason to hide it — and filtering here would make the absence indistinguishable from a
        program nobody created.
        """
        return await self._programs.list_for_department(command.department_id)
