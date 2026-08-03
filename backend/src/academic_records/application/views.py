"""Primitives-shaped projections of what this context's use cases return.

``StudentRecordView`` already keeps the ``AcademicRecord`` aggregate inside — "handing out an
``AcademicRecord`` would hand out ``record_grade`` and ``correct_grade`` along with it". What it
still carries is ``CourseGrade``, ``GradeCorrection``, ``Standing`` and a fistful of ``Decimal``,
and this is where those become strings and integers.

**CGPA and grade points cross as strings, not floats.** A CGPA is quantized to two decimal
places and half-up (``transcript.py``), and the probation threshold is judged on exactly that
reported figure. Handing the number to a transport that renders it as a binary float would
reintroduce the third decimal place the domain went to trouble to remove, and 1.50 is the
boundary a student is or is not on probation at. A string is what was decided; a float is a
re-derivation.
"""

from dataclasses import dataclass

from academic_records.application.correct_grade import GradeCorrected
from academic_records.application.read_academic_record import StudentRecordView
from academic_records.application.record_submitted_grade import GradeRecorded
from academic_records.domain.academic_record import GradeCorrection
from academic_records.domain.transcript import CourseGrade


@dataclass(frozen=True)
class CourseGradeView:
    """One transcript line: what was taken, when, and what it was worth."""

    course_id: str
    semester_id: str
    score: int
    credit_units: int
    letter: str
    grade_point: str
    is_pass: bool
    quality_points: str

    @classmethod
    def of(cls, grade: CourseGrade) -> "CourseGradeView":
        return cls(
            course_id=grade.course_id,
            semester_id=grade.semester_id,
            score=grade.score,
            credit_units=grade.credit_units,
            letter=grade.letter,
            grade_point=str(grade.grade_point),
            is_pass=grade.is_pass,
            quality_points=str(grade.quality_points),
        )


@dataclass(frozen=True)
class GradeCorrectionView:
    """One audit entry: what a grade was, what it became, why, and on whose authority."""

    course_id: str
    semester_id: str
    previous_score: int
    corrected_score: int
    reason: str
    authorized_by: str

    @classmethod
    def of(cls, correction: GradeCorrection) -> "GradeCorrectionView":
        return cls(
            course_id=correction.course_id,
            semester_id=correction.semester_id,
            previous_score=correction.previous_score,
            corrected_score=correction.corrected_score,
            reason=correction.reason,
            authorized_by=correction.authorized_by,
        )


@dataclass(frozen=True)
class AcademicRecordView:
    """A whole record, flat: every attempt ever recorded, and what it adds up to.

    ``grades`` holds every attempt, including a course failed and later passed — CLAUDE.md
    section 3's confirmed carry-over rule is that both lines stay and both count, so a view
    that collapsed them to a best attempt would be reporting a different CGPA from the one
    the probation decision was made on.
    """

    student_id: str
    cgpa: str
    standing: str
    total_units: int
    grades: tuple[CourseGradeView, ...]
    semester_gpas: dict[str, str]
    passed_course_ids: tuple[str, ...]
    corrections: tuple[GradeCorrectionView, ...]

    @classmethod
    def of(cls, record: StudentRecordView) -> "AcademicRecordView":
        return cls(
            student_id=record.student_id,
            cgpa=str(record.cgpa),
            standing=record.standing.value,
            total_units=record.total_units,
            grades=tuple(CourseGradeView.of(grade) for grade in record.grades),
            semester_gpas={
                semester_id: str(gpa) for semester_id, gpa in record.semester_gpas.items()
            },
            passed_course_ids=tuple(sorted(record.passed_course_ids)),
            corrections=tuple(
                GradeCorrectionView.of(correction) for correction in record.corrections
            ),
        )


@dataclass(frozen=True)
class GradeRecordedView:
    """What recording a submitted grade did.

    ``was_already_recorded`` distinguishes a first delivery from a redelivery, which is a
    no-op rather than a refusal: at-least-once delivery is normal, and the aggregate treats
    an identical redelivery as nothing having happened.
    """

    student_id: str
    grade: CourseGradeView
    was_already_recorded: bool

    @classmethod
    def of(cls, recorded: GradeRecorded) -> "GradeRecordedView":
        return cls(
            student_id=recorded.student_id,
            grade=CourseGradeView.of(recorded.grade),
            was_already_recorded=recorded.was_already_recorded,
        )


@dataclass(frozen=True)
class GradeCorrectedView:
    """What a correction changed, and what the record says now."""

    student_id: str
    correction: GradeCorrectionView
    cgpa: str
    standing: str

    @classmethod
    def of(cls, corrected: GradeCorrected) -> "GradeCorrectedView":
        return cls(
            student_id=corrected.student_id,
            correction=GradeCorrectionView.of(corrected.correction),
            cgpa=str(corrected.cgpa),
            standing=corrected.standing.value,
        )
