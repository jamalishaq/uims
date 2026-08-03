"""The real adapter behind ``StudentAcademicStandingPort``: a record, read as a standing.

Fed rather than reading Academic Records directly, for the reason rule (b) gives and the
``BillingFinancialClearanceAdapter`` pattern implements: the composition root calls
``ReadAcademicRecord.find`` and hands back the two facts below.

**No grade crosses this boundary, and that is the design.** ``ReadAcademicRecord`` answers with
a whole transcript — every attempt, every letter, a CGPA — and almost none of it is Enrollment's
business. What :class:`StudentRecord` carries is the set of courses passed and one enum, because
what counts as a pass is a grading-scale question that stays in Academic Records (CLAUDE.md
section 3), and the CGPA behind a probation decision is a number Enrollment is deliberately never
shown. A source that handed over letter grades would be pushing that judgement back across the
boundary for this context to re-make.

**A standing this context does not recognise reads as ``UNKNOWN``, never as an error.** Academic
Records has two standings and Enrollment's enum has three; the third exists for exactly this
gap. A refusal here would take a registration down over a vocabulary mismatch, and
``EligibilityRule`` already keys off nothing but the value — CLAUDE.md section 3: whether
probation lowers the credit-load cap is *not* decided.

**Absence is a fresher, not a refusal.** ``None`` means the student has no record, which
``RegisterForCourse`` turns into ``AcademicStanding.unrecorded``. A student registering for their
first course has never been graded, and that is the normal case rather than a missing row.
"""

from dataclasses import dataclass, field
from typing import Protocol

from enrollment.domain.facts import AcademicStanding, Standing
from enrollment.ports.student_academic_standing import StudentAcademicStandingPort

PROBATION = "probation"
"""The standing Academic Records reports for a student below the CGPA threshold.

Matched as a string rather than by importing that context's ``Standing``, which is not
importable from here. The two enums carry the same values by intent, and this constant is the
one place the correspondence is written down.
"""


@dataclass(frozen=True)
class StudentRecord:
    """What a record has to say about a student, in primitives, before it means anything here."""

    student_id: str
    passed_course_ids: frozenset[str] = field(default_factory=frozenset)
    standing: str = "good standing"


class StudentRecordSource(Protocol):
    """Whatever can say what a student has passed and how the university regards them."""

    async def student_record(self, student_id: str) -> StudentRecord | None:
        """The record, or ``None`` if the student has never been graded."""
        ...


class AcademicRecordsStandingAdapter(StudentAcademicStandingPort):
    """Reads Academic Records through a source, and answers in ``AcademicStanding``."""

    def __init__(self, source: StudentRecordSource) -> None:
        self._source = source

    async def standing_for(self, student_id: str) -> AcademicStanding | None:
        """The student's standing, or ``None`` if there is no record of them."""
        record = await self._source.student_record(student_id)
        if record is None:
            return None
        return AcademicStanding(
            student_id=record.student_id,
            passed_course_ids=frozenset(record.passed_course_ids),
            standing=self._standing(record.standing),
        )

    @staticmethod
    def _standing(reported: str) -> Standing:
        """Translate the reported standing, treating anything unrecognised as unknown."""
        if reported == PROBATION:
            return Standing.PROBATION
        if reported == Standing.GOOD_STANDING.value:
            return Standing.GOOD_STANDING
        return Standing.UNKNOWN
