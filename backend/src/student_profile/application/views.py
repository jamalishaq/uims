"""Primitives-shaped projections of what this context's use cases return.

``RegisterNewStudent`` hands back the ``Student`` aggregate. This is what leaves the building:
the matric number as the string it is written on an ID card, the level as the integer it is
spoken as, and the bio-data spread flat.

Nothing here parses a matric number back into its parts. ``matric_number.py`` is explicit that
nothing does — the number is issued by composing a format and read afterwards as one opaque
identifier, and a view that split it up would be a second, quieter implementation of the format.
"""

from dataclasses import dataclass
from datetime import date

from student_profile.domain.student import Student


@dataclass(frozen=True)
class StudentView:
    """One student, flat, with no way to correct their bio-data through it."""

    student_id: str
    matric_number: str
    program_id: str
    entry_session_id: str
    entry_level: int
    applicant_id: str | None
    full_name: str
    date_of_birth: date | None
    email: str | None
    phone_number: str | None

    @classmethod
    def of(cls, student: Student) -> "StudentView":
        """Project a student. The only place in this context that reads one field by field."""
        return cls(
            student_id=student.student_id,
            matric_number=str(student.matric_number),
            program_id=student.program_id,
            entry_session_id=student.entry_session_id,
            entry_level=student.entry_level.value,
            applicant_id=student.applicant_id,
            full_name=student.bio_data.full_name,
            date_of_birth=student.bio_data.date_of_birth,
            email=student.bio_data.email,
            phone_number=student.bio_data.phone_number,
        )
