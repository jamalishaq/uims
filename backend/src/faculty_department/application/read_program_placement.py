"""Read where a program sits and whether it is admitting, for one session.

**Why this use case exists.** Faculty & Department owns programs, departments and sessions, and
until now had exactly one use case — ``SubmitGrade``. Everything else reached its data through a
repository. That was fine while the only readers were tests, and stops being fine the moment two
other contexts need the same join: Admissions' ``ProgramInfoPort`` asks whether a program exists
and is admitting, Student Profile's ``DepartmentCodePort`` asks which department is behind it and
which year the session starts in. Both are the same three reads.

Without this, each of those adapters would have to be handed three repository ports by the
composition root and do the join itself — twice, in two contexts, over aggregates neither of them
may import. One read here, answered in this context's own published view, is the alternative.

**It is a read and nothing else.** No transition, no event, no write. ``find`` returns ``None``
for a program or session nobody has, because absence is a normal answer to a question about
identifiers a caller was handed by somebody else — the same shape ``ReadAccount.find`` and
``ReadAcademicRecord.find`` take, and for the same reason: the port adapters above it turn
``None`` into their own contexts' answers, and an exception here would make them catch to do it.
"""

from faculty_department.application.views import ProgramPlacementView
from faculty_department.ports.department_repository import DepartmentRepositoryPort
from faculty_department.ports.program_repository import ProgramRepositoryPort
from faculty_department.ports.session_repository import SessionRepositoryPort


class ReadProgramPlacement:
    """Answer where a program sits, in this context's own published shape."""

    def __init__(
        self,
        programs: ProgramRepositoryPort,
        departments: DepartmentRepositoryPort,
        sessions: SessionRepositoryPort,
    ) -> None:
        self._programs = programs
        self._departments = departments
        self._sessions = sessions

    async def find(self, program_id: str, session_id: str) -> ProgramPlacementView | None:
        """The placement, or ``None`` if the program, its department or the session is unknown.

        A program whose department is missing reads as unknown rather than as a partial answer.
        A placement is the join of the three, and half of one would have a caller building a
        matric number out of a department code that was never found.
        """
        program = await self._programs.get(program_id)
        if program is None:
            return None

        department = await self._departments.get(program.department_id)
        if department is None:
            return None

        session = await self._sessions.get(session_id)
        if session is None:
            return None

        return ProgramPlacementView(
            program_id=program.program_id,
            department_id=department.department_id,
            department_code=department.code,
            faculty_id=department.faculty_id,
            name=program.name,
            code=program.code,
            is_admitting=program.is_admitting,
            session_id=session.session_id,
            session_start_year=session.academic_year.start_year,
            session_label=session.academic_year.label,
            session_is_open=session.is_open,
        )
