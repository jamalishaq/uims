"""Academic Records inbound adapters.

One handler, and it is the reason this context exists at all: ``GradeSubmitted`` arrives
from Faculty & Department and becomes a line on a student's record. There is no HTTP
adapter here yet and no administrative interface — when one arrives it calls
``CorrectGrade`` and ``ReadAcademicRecord``, and the correction stays a human act rather
than something a publisher can trigger.
"""

from academic_records.adapters.inbound.grade_submitted_handler import (
    GRADE_SUBMITTED,
    GradeSubmittedHandler,
    GradeSubmittedMessage,
)

__all__ = [
    "GRADE_SUBMITTED",
    "GradeSubmittedHandler",
    "GradeSubmittedMessage",
]
