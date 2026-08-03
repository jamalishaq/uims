"""HTTP routes for Enrollment: one route, because this context does one thing.

``RegisterForCourse`` is the whole surface. There is deliberately no drop or withdraw route —
CLAUDE.md section 3: "there is deliberately no drop/withdraw state — when and how a course may
be dropped is an institutional fact nobody has stated." A route cannot be added for a use case
that does not exist, and inventing one here would be inventing the policy.

Schedule-blind, permanently: nothing on the request says when the course meets. Model A is a
permanent decision, not a gap.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from enrollment.adapters.inbound.http.schemas import (
    RegisterForCourseRequest,
    RegistrationAcceptedResponse,
    RegistrationRefusedResponse,
    RegistrationResponse,
)
from enrollment.application.register_for_course import (
    RegisterForCourse,
    RegisterForCourseCommand,
    RegistrationAccepted,
)
from enrollment.application.views import RegistrationAcceptedView, RegistrationRefusedView
from http_api import dependencies_of, error_responses

STATE_KEY = "enrollment"
"""Where this context's use cases hang on ``app.state``. Owned here, read by the root."""


class EnrollmentDependencies:
    """The use cases this router needs, wired once at startup."""

    def __init__(self, register_for_course: RegisterForCourse) -> None:
        self.register_for_course = register_for_course


def _deps(request: Request) -> EnrollmentDependencies:
    return dependencies_of(request, STATE_KEY, EnrollmentDependencies)


Deps = Annotated[EnrollmentDependencies, Depends(_deps)]

router = APIRouter(prefix="/enrollment", tags=["enrollment"])


@router.post(
    "/registrations",
    response_model=RegistrationResponse,
    summary="Register a student for a course",
    responses=error_responses(404, 409, 422, 500, 503),
)
async def register_for_course(body: RegisterForCourseRequest, deps: Deps) -> RegistrationResponse:
    """Register, or explain why not.

    **Both answers are 200.** A refusal is a decision the university made about a request it
    understood, not a malformed request, and the body says which happened in ``outcome``.
    A 4xx would also have to choose one status for a refusal that can have four separate
    causes at once.
    """
    outcome = await deps.register_for_course.execute(
        RegisterForCourseCommand.of(**body.model_dump())
    )
    if isinstance(outcome, RegistrationAccepted):
        return RegistrationAcceptedResponse.of(RegistrationAcceptedView.of(outcome))
    return RegistrationRefusedResponse.of(RegistrationRefusedView.of(outcome))


__all__ = ["STATE_KEY", "EnrollmentDependencies", "router"]
