"""HTTP routes for Faculty & Department: grade submission, and the placement read.

Two routes, and the small number is the honest report of this context's application layer
rather than a decision about its HTTP surface. Faculty & Department owns faculties,
departments, programs, lecturers and the academic calendar, and has **no use case that creates
any of them** — they are reachable only through repositories today. Routes to open a session,
create a program or assign a lecturer are use cases that do not exist yet, and writing them
here would be writing the application layer through the transport.

``SessionOpened`` is published when a session opens, and there is no route that opens one. That
is the same gap, seen from the other side.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from faculty_department.adapters.inbound.http.schemas import (
    GradeSubmittedResponse,
    ProgramPlacementResponse,
    SubmitGradeRequest,
)
from faculty_department.application.read_program_placement import ReadProgramPlacement
from faculty_department.application.submit_grade import SubmitGrade, SubmitGradeCommand
from faculty_department.application.views import GradeSubmittedView
from http_api import dependencies_of, error_responses

STATE_KEY = "faculty_department"
"""Where this context's use cases hang on ``app.state``. Owned here, read by the root."""


class FacultyDepartmentDependencies:
    """The use cases this router needs, wired once at startup."""

    def __init__(
        self,
        submit_grade: SubmitGrade,
        read_program_placement: ReadProgramPlacement,
    ) -> None:
        self.submit_grade = submit_grade
        self.read_program_placement = read_program_placement


def _deps(request: Request) -> FacultyDepartmentDependencies:
    return dependencies_of(request, STATE_KEY, FacultyDepartmentDependencies)


Deps = Annotated[FacultyDepartmentDependencies, Depends(_deps)]

router = APIRouter(prefix="/faculty-department", tags=["faculty-department"])


@router.post(
    "/grade-submissions",
    status_code=status.HTTP_201_CREATED,
    response_model=GradeSubmittedResponse,
    summary="Submit a grade for a student on a course",
    responses=error_responses(403, 404, 409, 422, 500, 503),
)
async def submit_grade(body: SubmitGradeRequest, deps: Deps) -> GradeSubmittedResponse:
    """Record a lecturer's mark and announce it.

    Publishing ``GradeSubmitted`` is part of the use case, so by the time this returns Academic
    Records has already consumed it — the bus is synchronous and a subscriber's failure is not
    swallowed. A 201 here therefore means the transcript line exists too.
    """
    event = await deps.submit_grade.execute(SubmitGradeCommand(**body.model_dump()))
    return GradeSubmittedResponse.of(GradeSubmittedView.of(event))


@router.get(
    "/programs/{program_id}/placement",
    response_model=ProgramPlacementResponse,
    summary="Read where a program sits, for one session",
    responses=error_responses(404, 422, 500, 503),
)
async def read_program_placement(
    program_id: str,
    session_id: Annotated[str, Query(description="The session the question is asked about.")],
    deps: Deps,
) -> ProgramPlacementResponse:
    """The program, its department and the session, joined.

    ``find`` answers ``None`` rather than raising, because its other callers — the adapters
    behind ``ProgramInfoPort`` and ``DepartmentCodePort`` — need the absence as a value. Over
    HTTP an absence is a 404, and this route is the one place that translation happens.
    """
    placement = await deps.read_program_placement.find(program_id, session_id)
    if placement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no placement for program {program_id!r} in session {session_id!r}",
        )
    return ProgramPlacementResponse.of(placement)


__all__ = ["STATE_KEY", "FacultyDepartmentDependencies", "router"]
