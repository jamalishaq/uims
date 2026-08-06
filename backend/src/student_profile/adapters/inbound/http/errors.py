"""Which status each of this context's refusals leaves as.

``ProgramPlacementUnknownError`` is a 422 and not a 404. The request named a program this
context cannot place — because Faculty & Department does not have it, or because its department
has no numeric code in the register the matric-number adapter was built with — and in every one
of those cases what is wrong is the request or the configuration behind it, not a missing
student. A 404 would say "no such student", which is the one thing that is certainly true and
entirely beside the point.
"""

from http_api import ExceptionStatuses
from student_profile.application.errors import (
    ApplicationError,
    ProgramPlacementUnknownError,
    StudentNotFoundError,
)
from student_profile.domain.errors import StudentProfileError
from student_profile.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
)

EXCEPTION_STATUSES: ExceptionStatuses = {
    # 404 — the student is not there.
    StudentNotFoundError: 404,
    AggregateNotFoundError: 404,
    # 409 — that id, or that matric number, is already held.
    DuplicateAggregateError: 409,
    # 422 — the request cannot describe a student this context can create.
    ProgramPlacementUnknownError: 422,
    StudentProfileError: 422,
    ApplicationError: 422,
    # 5xx — the store.
    PersistenceUnavailableError: 503,
    RepositoryError: 500,
}
