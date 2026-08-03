"""Which status each of this context's refusals leaves as.

``CourseCreditsUnavailableError`` is a **409, not a 404**, and it is the one entry here worth
arguing. The course the grade names is not missing from *this* context — nothing is missing
from this context — Course Catalog cannot say what the course is worth, and until it can, no
grade may be recorded against it. The application error's own docstring is blunt about the
stakes: "a transcript quietly wrong for four years". A 404 would tell a client the student or
the record was not found, sending whoever reads it to the wrong office entirely.
"""

from academic_records.application.errors import (
    AcademicRecordNotFoundError,
    AcademicRecordsApplicationError,
    CourseCreditsUnavailableError,
)
from academic_records.domain.errors import (
    AcademicRecordsError,
    GradeAlreadyRecordedError,
    GradeNotRecordedError,
    InvalidCorrectionError,
)
from academic_records.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
)
from http_api import ExceptionStatuses

EXCEPTION_STATUSES: ExceptionStatuses = {
    # 404 — this student has no record.
    AcademicRecordNotFoundError: 404,
    AggregateNotFoundError: 404,
    # 409 — the record is not in the state this request assumes, or a fact is unobtainable.
    GradeAlreadyRecordedError: 409,
    GradeNotRecordedError: 409,
    CourseCreditsUnavailableError: 409,
    DuplicateAggregateError: 409,
    # 422 — the correction cannot describe a correction.
    InvalidCorrectionError: 422,
    AcademicRecordsError: 422,
    AcademicRecordsApplicationError: 422,
    # 5xx — the store.
    PersistenceUnavailableError: 503,
    RepositoryError: 500,
}
