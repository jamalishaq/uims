"""Academic Records application layer.

Three use cases, and the shape of the set is the context's design in miniature. One is
driven by an event and happens constantly (:class:`RecordSubmittedGrade`); one is driven by
a human, needs a reason and a name, and should happen rarely (:class:`CorrectGrade`); one
only reads (:class:`ReadAcademicRecord`). That there is no fourth — no "recompute CGPA", no
"close semester", no "publish results" — is the point: an average is derived on read from
the lines, so there is no stored figure to fall out of step and no job that has to run for
a transcript to be right.

Orchestration only. Every rule these use cases appear to apply belongs to the domain: what
a mark is worth to the grading scale, whether a mark may be overwritten to the aggregate,
whether a CGPA means probation to the policy. What is decided here is what a use case is
allowed to decide — that a missing record on a first grade is a fresher and not a failure,
and that a course of unknown worth is refused rather than guessed at.
"""

from academic_records.application.correct_grade import (
    CorrectGrade,
    CorrectGradeCommand,
    GradeCorrected,
)
from academic_records.application.errors import (
    AcademicRecordNotFoundError,
    AcademicRecordsApplicationError,
    CourseCreditsUnavailableError,
)
from academic_records.application.read_academic_record import (
    ReadAcademicRecord,
    StudentRecordView,
)
from academic_records.application.record_submitted_grade import (
    GradeRecorded,
    RecordSubmittedGrade,
    RecordSubmittedGradeCommand,
)
from academic_records.application.views import (
    AcademicRecordView,
    CourseGradeView,
    GradeCorrectedView,
    GradeCorrectionView,
    GradeRecordedView,
)

__all__ = [
    "AcademicRecordNotFoundError",
    "AcademicRecordView",
    "AcademicRecordsApplicationError",
    "CorrectGrade",
    "CorrectGradeCommand",
    "CourseCreditsUnavailableError",
    "CourseGradeView",
    "GradeCorrected",
    "GradeCorrectedView",
    "GradeCorrectionView",
    "GradeRecorded",
    "GradeRecordedView",
    "ReadAcademicRecord",
    "RecordSubmittedGrade",
    "RecordSubmittedGradeCommand",
    "StudentRecordView",
]
