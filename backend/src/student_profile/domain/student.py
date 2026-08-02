"""The ``Student`` aggregate: the identity anchor the rest of the system points at.

Deliberately thin (CLAUDE.md section 3). Enrollment, Academic Records and Billing all
hold a student's identifier; almost nothing they know about the student belongs here.
Current level is the clearest example — it looks like it should be a field, but it is a
conclusion drawn from grades, and Academic Records owns that judgment. A copy kept here
would be a second answer to a question that already has one.

``program_id`` and ``entry_session_id`` are Faculty & Department's identifiers, opaque
to us. ``applicant_id`` is Admissions', and is present only on students who arrived by
matriculation: it is how Billing later finds the account it opened under that applicant
id and links it to a matric number (CLAUDE.md section 3, "party-id"). A student
registered by hand never had an applicant, and carries ``None``.

The matric number is fixed at creation and there is no setter. Reissuing one is not a
correction, it is a new identity, and it would have to be a deliberate administrative
act that every downstream context hears about.
"""

from student_profile.domain.errors import (
    InvalidBioDataError,
    InvalidLevelError,
    InvalidMatricNumberError,
)
from student_profile.domain.matric_number import MatricNumber
from student_profile.domain.values import BioData, Level, require_identifier


class Student:
    """A matriculated student."""

    def __init__(
        self,
        student_id: str,
        matric_number: MatricNumber,
        bio_data: BioData,
        program_id: str,
        entry_session_id: str,
        entry_level: Level,
        *,
        applicant_id: str | None = None,
    ) -> None:
        if not isinstance(matric_number, MatricNumber):
            raise InvalidMatricNumberError(
                "matric_number must be a MatricNumber issued by MatricNumberIssuer"
            )
        if not isinstance(bio_data, BioData):
            raise InvalidBioDataError("bio_data must be a BioData")
        if not isinstance(entry_level, Level):
            raise InvalidLevelError("entry_level must be a Level")
        self._student_id = require_identifier(student_id, "student_id")
        self._matric_number = matric_number
        self._bio_data = bio_data
        self._program_id = require_identifier(program_id, "program_id")
        self._entry_session_id = require_identifier(entry_session_id, "entry_session_id")
        self._entry_level = entry_level
        self._applicant_id = (
            None if applicant_id is None else require_identifier(applicant_id, "applicant_id")
        )

    @property
    def student_id(self) -> str:
        return self._student_id

    @property
    def matric_number(self) -> MatricNumber:
        return self._matric_number

    @property
    def bio_data(self) -> BioData:
        return self._bio_data

    @property
    def program_id(self) -> str:
        return self._program_id

    @property
    def entry_session_id(self) -> str:
        return self._entry_session_id

    @property
    def entry_level(self) -> Level:
        return self._entry_level

    @property
    def applicant_id(self) -> str | None:
        """The applicant this student was matriculated from, if they came that way."""
        return self._applicant_id

    def correct_bio_data(self, bio_data: BioData) -> None:
        """Replace the bio-data wholesale.

        A correction, not an update: bio-data is what the university was told about a
        person, and the whole of it is restated at once so a half-applied correction
        cannot leave a record that matches neither the old form nor the new one.
        """
        if not isinstance(bio_data, BioData):
            raise InvalidBioDataError("bio_data must be a BioData")
        self._bio_data = bio_data

    def __repr__(self) -> str:
        return (
            f"Student(student_id={self._student_id!r}, "
            f"matric_number={self._matric_number.value!r}, "
            f"entry_level={self._entry_level.value})"
        )
