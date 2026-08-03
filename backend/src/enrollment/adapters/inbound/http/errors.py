"""Which status each of this context's refusals leaves as.

Note what is *absent*: there is no entry for a refused registration. An unmet prerequisite, a
full course and an unpaid bill are not exceptions here — ``RegisterForCourse`` returns them —
and they leave as a 200 carrying every reason at once. Mapping them to a 4xx would contradict
the domain layer, which is explicit that they are normal outcomes, and would also force the
route to pick *one* status for a refusal that may have four causes.
"""

from enrollment.application.errors import (
    ApplicationError,
    CourseNotFoundError,
    CourseOfferingNotFoundError,
)
from enrollment.domain.errors import EnrollmentError
from enrollment.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
)
from http_api import ExceptionStatuses

EXCEPTION_STATUSES: ExceptionStatuses = {
    # 404 — the course, or the fact that it is run this term, is not there.
    CourseNotFoundError: 404,
    CourseOfferingNotFoundError: 404,
    AggregateNotFoundError: 404,
    # 409 — that enrollment id is already taken.
    DuplicateAggregateError: 409,
    # 422 — the request cannot describe a registration.
    EnrollmentError: 422,
    ApplicationError: 422,
    # 5xx — the store.
    PersistenceUnavailableError: 503,
    RepositoryError: 500,
}
