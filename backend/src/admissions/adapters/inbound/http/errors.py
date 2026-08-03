"""Which status each of this context's refusals leaves as.

``ProgramNotAdmittingError`` is a 422 rather than a 409, on the strength of its own docstring:
it calls itself "a submitted form failing validation". The program is real and the applicant
named it; what is wrong is the application, not the state of the world.

Screening and offer *outcomes* are absent from this table for the reason Enrollment's is:
``ApplicantNotQualified`` and ``NoOfferAvailable`` are returned, not raised, and leave as 200.
Quota exhaustion never surfaces at all — ``MakeOfferToApplicant`` handles it by looking at the
alternatives, which is the whole point of the flow.
"""

from admissions.application.errors import (
    AdmissionCycleNotFoundError,
    ApplicantNotFoundError,
    ApplicationError,
    EntryRequirementNotFoundError,
    ProgramNotAdmittingError,
    ProgramNotFoundError,
)
from admissions.domain.errors import (
    AdmissionsError,
    ApplicantAlreadyScreenedError,
    ApplicantNotScreenedError,
    ApplicationOutcomeFinalError,
    OfferAlreadyMadeError,
)
from admissions.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
)
from http_api import ExceptionStatuses

EXCEPTION_STATUSES: ExceptionStatuses = {
    # 404 — asked about something that is not there.
    ApplicantNotFoundError: 404,
    ProgramNotFoundError: 404,
    EntryRequirementNotFoundError: 404,
    AdmissionCycleNotFoundError: 404,
    AggregateNotFoundError: 404,
    # 409 — the application is not at the point this request assumes.
    ApplicantAlreadyScreenedError: 409,
    ApplicantNotScreenedError: 409,
    OfferAlreadyMadeError: 409,
    ApplicationOutcomeFinalError: 409,
    DuplicateAggregateError: 409,
    # 422 — the form is wrong.
    ProgramNotAdmittingError: 422,
    AdmissionsError: 422,
    ApplicationError: 422,
    # 5xx — the store.
    PersistenceUnavailableError: 503,
    RepositoryError: 500,
}
