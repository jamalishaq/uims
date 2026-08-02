"""The ``RegisterNewStudent`` use case: the one way a student comes into existence.

Both creation paths land here. An administrator registering a student by hand calls it
directly; Admissions' ``StudentMatriculated`` reaches it through the inbound handler,
which translates the event and calls this same use case with the same command. There is
deliberately no second path — a matriculation-only variant would be a second place where
a matric number is composed, and the two would drift.

Orchestration only. The composition rule lives in ``MatricNumberFormat`` and the counter
invariant lives in ``MatricSequence``; this module restates neither.

Order matters twice here. The command's own values are turned into value objects first,
so a blank name is rejected before anything irreversible happens. Then: claim the
ordinal, persist the counter, *and only then* store the student. Any other order can
leave a live student holding a number the counter will hand out again; this one can only
ever leave a gap.
"""

from dataclasses import dataclass
from datetime import date

from student_profile.application.errors import ProgramPlacementUnknownError
from student_profile.domain.matric_number_issuer import MatricNumberIssuer
from student_profile.domain.student import Student
from student_profile.domain.values import BioData, Level
from student_profile.ports.department_code import DepartmentCodePort
from student_profile.ports.matric_sequence_repository import MatricSequenceRepositoryPort
from student_profile.ports.student_repository import StudentRepositoryPort

DEFAULT_ENTRY_LEVEL = 100
"""Where a student starts unless told otherwise. Direct entry is passed explicitly."""


@dataclass(frozen=True)
class RegisterNewStudentCommand:
    """What an inbound adapter must supply to register one student.

    No matric number: it is this context's to issue, and a command that could carry one
    would be a way for a caller to bring its own.

    ``applicant_id`` is set only by the matriculation path. A student registered by hand
    never had an applicant, and carrying ``None`` says so honestly.
    """

    student_id: str
    program_id: str
    entry_session_id: str
    full_name: str
    date_of_birth: date | None = None
    email: str | None = None
    phone_number: str | None = None
    entry_level: int = DEFAULT_ENTRY_LEVEL
    applicant_id: str | None = None


class RegisterNewStudent:
    """Issue a matric number and create the student who holds it."""

    def __init__(
        self,
        students: StudentRepositoryPort,
        sequences: MatricSequenceRepositoryPort,
        departments: DepartmentCodePort,
        issuer: MatricNumberIssuer,
    ) -> None:
        self._students = students
        self._sequences = sequences
        self._departments = departments
        self._issuer = issuer

    def execute(self, command: RegisterNewStudentCommand) -> Student:
        """Store and return the new student.

        Raises:
            ProgramPlacementUnknownError: Faculty & Department could not resolve the
                program and session into a department code and an entry year.
            DuplicateAggregateError: the student id is already held.
            StudentProfileError: the bio-data, the level or an identifier is invalid.
                Domain errors pass through untranslated — the domain already says exactly
                what went wrong.
        """
        bio_data = BioData(
            full_name=command.full_name,
            date_of_birth=command.date_of_birth,
            email=command.email,
            phone_number=command.phone_number,
        )
        entry_level = Level(command.entry_level)

        inputs = self._departments.format_inputs_for(command.program_id, command.entry_session_id)
        if inputs is None:
            raise ProgramPlacementUnknownError(
                f"no department code or entry year is known for program "
                f"{command.program_id!r} in session {command.entry_session_id!r}"
            )

        sequence = self._sequences.get_or_start(inputs.department_code, inputs.entry_year)
        matric_number = self._issuer.issue(sequence)
        self._sequences.save(sequence)

        student = Student(
            student_id=command.student_id,
            matric_number=matric_number,
            bio_data=bio_data,
            program_id=command.program_id,
            entry_session_id=command.entry_session_id,
            entry_level=entry_level,
            applicant_id=command.applicant_id,
        )
        self._students.add(student)
        return student
