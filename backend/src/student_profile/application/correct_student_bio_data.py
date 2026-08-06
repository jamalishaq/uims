"""Correcting what the university holds about a student.

``Student.correct_bio_data`` has been on the aggregate since the first phase with nothing in
front of it. Names are misspelled on application forms, and a system that could issue a
permanent identifier around a name but never fix the name is a system that makes somebody
live with a typo for four years.

**A correction, not a rename.** The matric number does not move — it encodes entry year and
department, neither of which bio-data touches — and nothing is published. No other context
holds a copy of a student's name to keep in step: Admissions has its own ``BioData`` from the
application and that is a record of what was submitted, which a later correction here should
*not* rewrite.

Unlike ``CorrectGrade`` in Academic Records, this demands no reason and no authorizer. The
asymmetry is deliberate: a transcript is evidence somebody else relies on, so changing one is
an act that has to be accounted for. A misspelled surname is the university being wrong about
a person, and making them file a justification to be spelled correctly would be the wrong
shape of respect.
"""

from dataclasses import dataclass
from datetime import date

from student_profile.application.errors import StudentNotFoundError
from student_profile.domain.student import Student
from student_profile.domain.values import BioData
from student_profile.ports.student_repository import StudentRepositoryPort


@dataclass(frozen=True)
class CorrectStudentBioDataCommand:
    """Who to correct, and what the record should now say.

    A replacement rather than a patch: the three optional fields **clear** when omitted, for
    ``AmendLecturerProfile``'s reason — this is a form being saved, and a caller that wanted to
    change only a name would send the rest back unchanged.
    """

    student_id: str
    full_name: str
    date_of_birth: date | None = None
    email: str | None = None
    phone_number: str | None = None


class CorrectStudentBioData:
    """Fix what the university holds about a student."""

    def __init__(self, students: StudentRepositoryPort) -> None:
        self._students = students

    async def execute(self, command: CorrectStudentBioDataCommand) -> Student:
        """Replace the bio-data and store the student.

        One aggregate, so there is no ordering to argue about and nothing to publish.

        Raises:
            StudentNotFoundError: no student is stored under that id.
            InvalidBioDataError: the name is blank, or the date of birth is not in the past.
        """
        student = await self._students.get(command.student_id)
        if student is None:
            raise StudentNotFoundError(f"no student stored with id {command.student_id!r}")

        student.correct_bio_data(
            BioData(
                full_name=command.full_name,
                date_of_birth=command.date_of_birth,
                email=command.email,
                phone_number=command.phone_number,
            )
        )
        await self._students.save(student)
        return student
