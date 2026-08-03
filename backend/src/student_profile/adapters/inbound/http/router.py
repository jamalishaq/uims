"""HTTP routes for Student Profile: the manual registration path.

``adapters/inbound/__init__.py`` predicted this file exactly — "An HTTP adapter for the manual
registration path is a later phase and will call the same ``RegisterNewStudent``" — and that is
what it does. The event-driven path (``StudentMatriculated`` arriving from Admissions) still
goes through ``StudentMatriculatedHandler``, and both end at the same issuer, which is the
invariant Phase 2 was built around.

One route. This context is deliberately thin: it is the identity anchor other contexts
reference by id, and it has no use case for correcting bio-data or changing level.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from http_api import dependencies_of, error_responses
from student_profile.adapters.inbound.http.schemas import (
    RegisterNewStudentRequest,
    StudentResponse,
)
from student_profile.application.register_new_student import (
    RegisterNewStudent,
    RegisterNewStudentCommand,
)
from student_profile.application.views import StudentView

STATE_KEY = "student_profile"
"""Where this context's use cases hang on ``app.state``. Owned here, read by the root."""


class StudentProfileDependencies:
    """The use cases this router needs, wired once at startup."""

    def __init__(self, register_new_student: RegisterNewStudent) -> None:
        self.register_new_student = register_new_student


def _deps(request: Request) -> StudentProfileDependencies:
    return dependencies_of(request, STATE_KEY, StudentProfileDependencies)


Deps = Annotated[StudentProfileDependencies, Depends(_deps)]

router = APIRouter(prefix="/student-profile", tags=["student-profile"])


@router.post(
    "/students",
    status_code=status.HTTP_201_CREATED,
    response_model=StudentResponse,
    summary="Register a student, issuing their matric number",
    responses=error_responses(409, 422, 500, 503),
)
async def register_new_student(body: RegisterNewStudentRequest, deps: Deps) -> StudentResponse:
    """Create the student and issue their matric number in one operation.

    The number is not in the request and cannot be: it is composed from the department's code
    and the entry year, against a counter that survives restarts precisely so two students
    never share one.
    """
    student = await deps.register_new_student.execute(
        RegisterNewStudentCommand(**body.model_dump())
    )
    return StudentResponse.of(StudentView.of(student))


__all__ = ["STATE_KEY", "StudentProfileDependencies", "router"]
