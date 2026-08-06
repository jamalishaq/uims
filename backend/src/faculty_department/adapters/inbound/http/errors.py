"""Which status each of this context's refusals leaves as.

``LecturerNotAssignedToCourseError`` is a 403 and the only one in the system. Every other
refusal here is about the shape of a request or the state of a session; this one is about
*authority* — the lecturer exists, the course exists, the session is open, and this person may
not grade that course. CLAUDE.md section 3 calls it the act this context owns: "a lecturer
acting on their course", checked against data it already holds. A 409 would file it with the
state errors and lose the distinction; a 422 would suggest the request could be rewritten into
an acceptable one, which is exactly what must not happen.

It is worth being clear about what this 403 is not: there is no authentication in this phase, so
it says the *named* lecturer is not assigned, not that the caller is not the lecturer. Anyone
who can reach this endpoint can submit a grade as any lecturer who is assigned.
"""

from faculty_department.application.errors import (
    ApplicationError,
    DepartmentNotFoundError,
    FacultyNotFoundError,
    LecturerNotFoundError,
    ProgramNotFoundError,
    SessionNotFoundError,
)
from faculty_department.domain.errors import (
    DuplicateCourseAssignmentError,
    FacultyDepartmentError,
    LecturerNotAssignedToCourseError,
    SemesterNotInSessionError,
    SessionAlreadyClosedError,
    SessionAlreadyOpenError,
    SessionNotOpenError,
)
from faculty_department.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
)
from http_api import ExceptionStatuses

EXCEPTION_STATUSES: ExceptionStatuses = {
    # 403 — the lecturer does not teach that course.
    LecturerNotAssignedToCourseError: 403,
    # 404 — asked about something that is not there. The three structural misses are what a
    # creation route answers when it names a level above it that nobody has.
    LecturerNotFoundError: 404,
    SessionNotFoundError: 404,
    FacultyNotFoundError: 404,
    DepartmentNotFoundError: 404,
    ProgramNotFoundError: 404,
    AggregateNotFoundError: 404,
    # 409 — the calendar is not where this request assumes.
    SessionNotOpenError: 409,
    SessionAlreadyOpenError: 409,
    SessionAlreadyClosedError: 409,
    SemesterNotInSessionError: 409,
    DuplicateCourseAssignmentError: 409,
    DuplicateAggregateError: 409,
    # 422 — the submission cannot describe a grade.
    FacultyDepartmentError: 422,
    ApplicationError: 422,
    # 5xx — the store.
    PersistenceUnavailableError: 503,
    RepositoryError: 500,
}
