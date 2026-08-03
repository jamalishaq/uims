"""Academic Records domain layer.

Owns what a mark is worth. The grading scale, the weighted average that turns a set of
marks into a GPA and a CGPA, the threshold that turns a CGPA into a standing, and the rule
that a recorded grade does not change — all of it here, and none of it anywhere else in
the system. Faculty & Department publishes a raw score and says in its own value object
that turning one into a letter "is a grading scale, which Academic Records owns";
Enrollment's port docstring says a prerequisite rule written against letter grades would be
that context acquiring an opinion it should not have. This package is what both of them are
pointing at.

Built from events, not queries. The record exists because ``GradeSubmitted`` arrived, and
this context asks Enrollment nothing — not whether the student was registered, not what
their load was (CLAUDE.md section 3). The one thing it does have to ask anybody is what a
course is worth, because a CGPA is weighted by credit units and the event does not carry
them; that arrives as :class:`CourseCredits` through a port, and is snapshotted onto the
line so a re-valued course cannot rewrite a transcript already issued.

Stdlib only: no persistence, no ports, no HTTP reaches this package. ``decimal`` and not
``float`` throughout — a CGPA is arithmetic somebody checks by hand.

Two settled institutional facts live here as named constants rather than as literals inside
rules, in the manner of Student Profile's matric number format and Enrollment's 24-unit
cap: :data:`LASU_GRADING_SCALE` and :data:`PROBATION_CGPA_THRESHOLD`. Both were confirmed
with a human (CLAUDE.md section 6), and both are construction arguments, so changing either
is an argument at a call site.
"""

from academic_records.domain.academic_record import AcademicRecord, GradeCorrection
from academic_records.domain.errors import (
    AcademicRecordsError,
    GradeAlreadyRecordedError,
    GradeNotRecordedError,
    InvalidCorrectionError,
    InvalidCreditUnitsError,
    InvalidGradingScaleError,
    InvalidProbationPolicyError,
    InvalidScoreError,
    MissingIdentifierError,
)
from academic_records.domain.facts import CourseCredits
from academic_records.domain.grading_scale import (
    LASU_GRADING_SCALE,
    AwardedGrade,
    GradeBand,
    GradingScale,
)
from academic_records.domain.probation import (
    PROBATION_CGPA_THRESHOLD,
    ProbationPolicy,
    Standing,
)
from academic_records.domain.transcript import CourseGrade, Transcript
from academic_records.domain.values import MAX_SCORE, MIN_SCORE

__all__ = [
    "LASU_GRADING_SCALE",
    "MAX_SCORE",
    "MIN_SCORE",
    "PROBATION_CGPA_THRESHOLD",
    "AcademicRecord",
    "AcademicRecordsError",
    "AwardedGrade",
    "CourseCredits",
    "CourseGrade",
    "GradeAlreadyRecordedError",
    "GradeBand",
    "GradeCorrection",
    "GradeNotRecordedError",
    "GradingScale",
    "InvalidCorrectionError",
    "InvalidCreditUnitsError",
    "InvalidGradingScaleError",
    "InvalidProbationPolicyError",
    "InvalidScoreError",
    "MissingIdentifierError",
    "ProbationPolicy",
    "Standing",
    "Transcript",
]
