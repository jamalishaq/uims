"""Which status each of this context's refusals leaves as.

Per context and not centrally, because the seven error vocabularies share no base class:
``CourseNotFoundError`` here and ``CourseNotFoundError`` in Enrollment are unrelated classes,
and a single table naming both would be a module importing two contexts. The mechanism is in
``http_api``; the vocabulary is here, next to the context that speaks it.

Bases are listed alongside their subclasses on purpose. ``http_api`` matches along the MRO,
most specific first, so ``CourseCatalogError`` catching everything at 422 is a floor rather
than a ceiling — a new domain error is a validation failure by default, which is the safe way
round for a rule nobody has classified yet.
"""

from course_catalog.application.errors import (
    ApplicationError,
    CourseNotFoundError,
    DuplicateCourseCodeError,
    PrerequisiteCourseNotFoundError,
)
from course_catalog.domain.errors import (
    CourseCatalogError,
    DuplicatePrerequisiteError,
    PrerequisiteCycleError,
    PrerequisiteNotRequiredError,
    SelfPrerequisiteError,
)
from course_catalog.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
)
from http_api import ExceptionStatuses

EXCEPTION_STATUSES: ExceptionStatuses = {
    # 404 — asked about something that is not there.
    CourseNotFoundError: 404,
    PrerequisiteCourseNotFoundError: 404,
    AggregateNotFoundError: 404,
    # 409 — the request is well formed and contradicts what is already true.
    DuplicateCourseCodeError: 409,
    DuplicateAggregateError: 409,
    SelfPrerequisiteError: 409,
    DuplicatePrerequisiteError: 409,
    PrerequisiteNotRequiredError: 409,
    PrerequisiteCycleError: 409,
    # 422 — the request cannot describe a course at all.
    CourseCatalogError: 422,
    ApplicationError: 422,
    # 503 — the store could not be reached, after three attempts.
    PersistenceUnavailableError: 503,
    RepositoryError: 500,
}
