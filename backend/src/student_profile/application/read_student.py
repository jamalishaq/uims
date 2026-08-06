"""Reading a student back.

Student Profile has had one use case since its first phase — ``RegisterNewStudent`` — and no
way to read what it created. That is the gap this closes: a matric number was issued and
stored, and nothing could show it to the person it belongs to.

Three ways in, because a student is known by three different names depending on who is
asking. Admissions knows an ``applicant_id``, the bursary and the gateway quote a matric
number, and everything inside this system uses the ``student_id`` this context minted. All
three are on the port already; none had a caller.

``find`` answers ``None`` rather than raising, in the manner of ``ReadAccount.find``: absence
is a normal answer to a question about an identifier a caller was handed by somebody else.
"""

from student_profile.domain.errors import InvalidMatricNumberError
from student_profile.domain.matric_number import MatricNumber
from student_profile.domain.student import Student
from student_profile.ports.student_repository import StudentRepositoryPort


class ReadStudent:
    """One student, by whichever identifier the caller holds."""

    def __init__(self, students: StudentRepositoryPort) -> None:
        self._students = students

    async def find(self, student_id: str) -> Student | None:
        """By this context's own identifier."""
        return await self._students.get(student_id)

    async def find_by_matric_number(self, matric_number: str) -> Student | None:
        """By the number on their ID card.

        A string that is not a matric number at all reads as ``None`` rather than raising:
        the caller typed something into a lookup box, and "no student with that number" is the
        honest answer to a number nobody could hold. The catch is narrow —
        ``InvalidMatricNumberError`` and nothing else — because a broad one here would swallow
        a repository that was down and report it as an unknown student (CLAUDE.md section 4).
        """
        try:
            parsed = MatricNumber(matric_number)
        except InvalidMatricNumberError:
            return None
        return await self._students.find_by_matric_number(parsed)

    async def find_by_applicant(self, applicant_id: str) -> Student | None:
        """By the id Admissions knew them as, which is how a client follows a matriculation."""
        return await self._students.find_by_applicant(applicant_id)
