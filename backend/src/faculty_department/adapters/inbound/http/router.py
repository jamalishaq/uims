"""HTTP routes for Faculty & Department: the academic structure, the calendar, and grading.

This context owns faculties, departments, programs, lecturers and the academic calendar — the
most-queried data in the system — and for five phases had **no use case that created any of
them**. They were reachable only by writing rows into Postgres by hand. The creation routes
here are that gap closed, and each checks the level above it so a typo becomes a 404 rather
than a dangling reference that surfaces much later as an applicant being told their program
does not exist.

**Opening a session bills a cohort.** ``POST /sessions/{id}/opening`` is the only publisher of
``SessionOpened`` in the system; Billing charges every active account the session's fee on it.
The subscription had been wired for phases with nothing to trigger it.

**Unauthenticated in this phase.** Every route here rewrites the university's structure or its
calendar, and anyone who can reach the process can call them.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from faculty_department.adapters.inbound.http.schemas import (
    CreateDepartmentRequest,
    CreateFacultyRequest,
    CreateProgramRequest,
    DepartmentResponse,
    FacultyResponse,
    GradeSubmittedResponse,
    LecturerResponse,
    PlanSessionRequest,
    ProgramListResponse,
    ProgramPlacementResponse,
    ProgramResponse,
    RegisterLecturerRequest,
    SessionResponse,
    SetProgramAdmissionsRequest,
    SubmitGradeRequest,
)
from faculty_department.application.create_structure import (
    CreateDepartment,
    CreateDepartmentCommand,
    CreateFaculty,
    CreateFacultyCommand,
    CreateProgram,
    CreateProgramCommand,
    SetProgramAdmissions,
    SetProgramAdmissionsCommand,
)
from faculty_department.application.list_department_programs import (
    ListDepartmentPrograms,
    ListDepartmentProgramsCommand,
)
from faculty_department.application.manage_calendar import (
    OpenSession,
    OpenSessionCommand,
    PlannedSemester,
    PlanSession,
    PlanSessionCommand,
)
from faculty_department.application.read_program_placement import ReadProgramPlacement
from faculty_department.application.register_lecturer import (
    RegisterLecturer,
    RegisterLecturerCommand,
)
from faculty_department.application.submit_grade import SubmitGrade, SubmitGradeCommand
from faculty_department.application.views import (
    DepartmentView,
    FacultyView,
    GradeSubmittedView,
    LecturerView,
    ProgramView,
    SessionView,
)
from http_api import dependencies_of, error_responses

STATE_KEY = "faculty_department"
"""Where this context's use cases hang on ``app.state``. Owned here, read by the root."""


class FacultyDepartmentDependencies:
    """The use cases this router needs, wired once at startup."""

    def __init__(
        self,
        submit_grade: SubmitGrade,
        read_program_placement: ReadProgramPlacement,
        create_faculty: CreateFaculty,
        create_department: CreateDepartment,
        create_program: CreateProgram,
        set_program_admissions: SetProgramAdmissions,
        list_department_programs: ListDepartmentPrograms,
        plan_session: PlanSession,
        open_session: OpenSession,
        register_lecturer: RegisterLecturer,
    ) -> None:
        self.submit_grade = submit_grade
        self.read_program_placement = read_program_placement
        self.create_faculty = create_faculty
        self.create_department = create_department
        self.create_program = create_program
        self.set_program_admissions = set_program_admissions
        self.list_department_programs = list_department_programs
        self.plan_session = plan_session
        self.open_session = open_session
        self.register_lecturer = register_lecturer


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


# ---- the academic structure ----


@router.post(
    "/faculties",
    status_code=status.HTTP_201_CREATED,
    response_model=FacultyResponse,
    summary="Create a faculty",
    responses=error_responses(409, 422, 500, 503),
)
async def create_faculty(body: CreateFacultyRequest, deps: Deps) -> FacultyResponse:
    """The top of the structure. Departments reference it by id."""
    faculty = await deps.create_faculty.execute(
        CreateFacultyCommand(faculty_id=body.faculty_id, name=body.name, code=body.code)
    )
    return FacultyResponse.of(FacultyView.of(faculty))


@router.post(
    "/departments",
    status_code=status.HTTP_201_CREATED,
    response_model=DepartmentResponse,
    summary="Create a department in a faculty",
    responses=error_responses(404, 409, 422, 500, 503),
)
async def create_department(body: CreateDepartmentRequest, deps: Deps) -> DepartmentResponse:
    """A 404 means the faculty does not exist — checked so a typo cannot become a department
    hanging off nothing, which would surface later as a placement that cannot be read."""
    department = await deps.create_department.execute(
        CreateDepartmentCommand(
            department_id=body.department_id,
            faculty_id=body.faculty_id,
            name=body.name,
            code=body.code,
        )
    )
    return DepartmentResponse.of(DepartmentView.of(department))


@router.post(
    "/programs",
    status_code=status.HTTP_201_CREATED,
    response_model=ProgramResponse,
    summary="Create a program in a department",
    responses=error_responses(404, 409, 422, 500, 503),
)
async def create_program(body: CreateProgramRequest, deps: Deps) -> ProgramResponse:
    """Created **not admitting**. Opening the window is a separate decision, so a program
    cannot start taking applications as a side effect of being described."""
    program = await deps.create_program.execute(
        CreateProgramCommand(
            program_id=body.program_id,
            department_id=body.department_id,
            name=body.name,
            code=body.code,
        )
    )
    return ProgramResponse.of(ProgramView.of(program))


@router.put(
    "/programs/{program_id}/admissions",
    response_model=ProgramResponse,
    summary="Open or close a program's admissions window",
    responses=error_responses(404, 422, 500, 503),
)
async def set_program_admissions(
    program_id: str, body: SetProgramAdmissionsRequest, deps: Deps
) -> ProgramResponse:
    """``PUT`` because it sets a state rather than requesting a transition: asking for a
    program to be admitting when it already is succeeds and changes nothing.

    Session-less, as this context holds it. Admissions asks per session and reconciles the two
    — a program is admitting *for a session* only when this flag is set and that session is
    open — so this is one half of that answer.
    """
    program = await deps.set_program_admissions.execute(
        SetProgramAdmissionsCommand(program_id=program_id, is_admitting=body.is_admitting)
    )
    return ProgramResponse.of(ProgramView.of(program))


@router.get(
    "/departments/{department_id}/programs",
    response_model=ProgramListResponse,
    summary="List a department's programs",
    responses=error_responses(422, 500, 503),
)
async def list_department_programs(department_id: str, deps: Deps) -> ProgramListResponse:
    """The inverse of the placement read, and how a client relates people to a department.

    An ``Applicant`` carries programs and never a department. A caller wanting "my
    department's applicants" reads this list and then asks Admissions per program — two calls,
    and Admissions is spared a notion of departments it has no other reason to hold.

    A department nobody has is an empty list, not a 404: the use case raises nothing, and an
    unknown department is indistinguishable from one that offers nothing yet.
    """
    programs = await deps.list_department_programs.execute(
        ListDepartmentProgramsCommand(department_id=department_id)
    )
    return ProgramListResponse(
        programs=tuple(ProgramResponse.of(view) for view in ProgramView.of_each(programs))
    )


# ---- the academic calendar ----


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionResponse,
    summary="Plan an academic session",
    responses=error_responses(409, 422, 500, 503),
)
async def plan_session(body: PlanSessionRequest, deps: Deps) -> SessionResponse:
    """Describe a session before it starts. Nothing is charged and nothing is announced."""
    session = await deps.plan_session.execute(
        PlanSessionCommand(
            session_id=body.session_id,
            academic_year=body.academic_year,
            semesters=tuple(
                PlannedSemester(semester_id=semester.semester_id, ordinal=semester.ordinal)
                for semester in body.semesters
            ),
        )
    )
    return SessionResponse.of(SessionView.of(session))


@router.post(
    "/sessions/{session_id}/opening",
    response_model=SessionResponse,
    summary="Open a planned session",
    responses=error_responses(404, 409, 422, 500, 503),
)
async def open_session(session_id: str, deps: Deps) -> SessionResponse:
    """**This bills a cohort.** Opening publishes ``SessionOpened``, and Billing charges every
    active account what the session's fee schedule says its program and level costs.

    Delivery is synchronous, so a fee schedule that cannot price a session takes this request
    down with it — which is wanted: a session recorded as open that nobody was billed for is
    the state an administrator has to notice, and a 200 would hide it.

    A 409 means the session has already been opened, or has closed.
    """
    session = await deps.open_session.execute(OpenSessionCommand(session_id=session_id))
    return SessionResponse.of(SessionView.of(session))


# ---- staff ----


@router.post(
    "/lecturers",
    status_code=status.HTTP_201_CREATED,
    response_model=LecturerResponse,
    summary="Register a lecturer in a department",
    responses=error_responses(404, 409, 422, 500, 503),
)
async def register_lecturer(body: RegisterLecturerRequest, deps: Deps) -> LecturerResponse:
    """The other half of ``SubmitGrade``'s authorization, which asks a stored lecturer whether
    they teach the course. Created teaching nothing: who teaches what is decided again every
    session and moves separately.
    """
    lecturer = await deps.register_lecturer.execute(
        RegisterLecturerCommand(
            lecturer_id=body.lecturer_id,
            department_id=body.department_id,
            full_name=body.full_name,
        )
    )
    return LecturerResponse.of(LecturerView.of(lecturer))
