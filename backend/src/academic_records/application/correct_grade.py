"""Correct a recorded grade. The one and only way a finalized grade ever changes.

CLAUDE.md section 3: "Finalized grades are effectively immutable; corrections are explicit
administrative acts." This module is the *explicit* part. There is no other path — no
setter on the aggregate, no second delivery of ``GradeSubmitted`` that overwrites, no
repository method that replaces a record wholesale. A registry that wants a mark changed
comes through here, and the change costs them a reason and their name.

Deliberately **not** driven by an event. A correction is a human act by somebody with the
authority to make it, and an inbound bus adapter carrying one would mean any publisher
could rewrite a transcript. It is a use case an administrative interface calls, in the way
``matriculate()`` is a human-triggered use case rather than a reaction to payment
(CLAUDE.md section 3).

Nothing is published afterwards, either. Enrollment pulls a student's standing when it
needs it and will see the corrected CGPA on its next read; announcing it would be this
context acquiring an audience it does not have.
"""

from dataclasses import dataclass
from decimal import Decimal

from academic_records.application.errors import AcademicRecordNotFoundError
from academic_records.domain.academic_record import GradeCorrection
from academic_records.domain.probation import Standing
from academic_records.ports.academic_record_repository import AcademicRecordRepositoryPort


@dataclass(frozen=True)
class CorrectGradeCommand:
    """A registry's instruction to change one recorded mark.

    ``reason`` and ``authorized_by`` have no defaults and are not optional. A correction
    with a blank reason is indistinguishable, a year later, from a data-entry error nobody
    noticed, and the audit trail exists precisely to tell those apart.
    """

    student_id: str
    course_id: str
    semester_id: str
    corrected_score: int
    reason: str
    authorized_by: str


@dataclass(frozen=True)
class GradeCorrected:
    """What changed, and what it did to the student's headline numbers.

    Carries the CGPA and standing *after* the correction, because the reason anyone
    corrects a grade is what it does to those two, and a caller that had to re-read the
    record to find out would be making a second round trip for the answer to the question
    they just asked.
    """

    student_id: str
    correction: GradeCorrection
    cgpa: Decimal
    standing: Standing


class CorrectGrade:
    """An administrator changes a grade that has already been recorded."""

    def __init__(self, records: AcademicRecordRepositoryPort) -> None:
        self._records = records

    async def execute(self, command: CorrectGradeCommand) -> GradeCorrected:
        """Apply the correction and store the record.

        Raises:
            AcademicRecordNotFoundError: no record is stored for that student.
            GradeNotRecordedError: the record holds no grade for that course in that
                semester, so there is nothing to correct.
            InvalidCorrectionError: the reason or authorizer is blank, or the corrected
                score is the one already recorded.
            AcademicRecordsError: the score or an identifier is invalid.
        """
        record = await self._records.get(command.student_id)
        if record is None:
            raise AcademicRecordNotFoundError(
                f"no academic record is stored for student {command.student_id!r}"
            )

        correction = record.correct_grade(
            course_id=command.course_id,
            semester_id=command.semester_id,
            corrected_score=command.corrected_score,
            reason=command.reason,
            authorized_by=command.authorized_by,
        )
        await self._records.save(record)

        return GradeCorrected(
            student_id=record.student_id,
            correction=correction,
            cgpa=record.cgpa,
            standing=record.standing,
        )
