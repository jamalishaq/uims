"""HTTP routes for Student Profile: the manual registration path.

``adapters/inbound/__init__.py`` predicted this file exactly — "An HTTP adapter for the manual
registration path is a later phase and will call the same ``RegisterNewStudent``" — and that is
what it does. The event-driven path (``StudentMatriculated`` arriving from Admissions) still
goes through ``StudentMatriculatedHandler``, and both end at the same issuer, which is the
invariant Phase 2 was built around.

**This context stays thin, and the routes reflect that.** It is the identity anchor other
contexts reference by id: it registers a student, shows one, and fixes a misspelled name.
Everything a student *portal* displays — their record, their ledger, their registrations —
belongs to Academic Records, Billing and Enrollment, and is composed by the client from those
routes. A read here that assembled them would be one module knowing four contexts, which only
the composition root may be.

A student is looked up by any of three identifiers, because that is how many names they have:
the ``student_id`` this context minted, the matric number the bursary and the gateway quote,
and the ``applicant_id`` Admissions knew them by — which is how a client follows a
matriculation to the student it produced, since nothing is published back.

**There is no route that changes a level.** What advances a student's level and when is an
institutional fact nobody has stated (CLAUDE.md section 6), and a route would have to invent
one.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

import security
from http_api import dependencies_of, error_responses
from student_profile.adapters.inbound.http.schemas import (
    CorrectStudentBioDataRequest,
    RegisterNewStudentRequest,
    StudentResponse,
)
from student_profile.application.correct_student_bio_data import (
    CorrectStudentBioData,
    CorrectStudentBioDataCommand,
)
from student_profile.application.read_student import ReadStudent
from student_profile.application.register_new_student import (
    RegisterNewStudent,
    RegisterNewStudentCommand,
)
from student_profile.application.views import StudentView

STATE_KEY = "student_profile"
"""Where this context's use cases hang on ``app.state``. Owned here, read by the root."""


class StudentProfileDependencies:
    """The use cases this router needs, wired once at startup."""

    def __init__(
        self,
        register_new_student: RegisterNewStudent,
        read_student: ReadStudent,
        correct_student_bio_data: CorrectStudentBioData,
    ) -> None:
        self.register_new_student = register_new_student
        self.read_student = read_student
        self.correct_student_bio_data = correct_student_bio_data


def _deps(request: Request) -> StudentProfileDependencies:
    return dependencies_of(request, STATE_KEY, StudentProfileDependencies)


Deps = Annotated[StudentProfileDependencies, Depends(_deps)]

router = APIRouter(prefix="/student-profile", tags=["student-profile"])


@router.post(
    "/students",
    status_code=status.HTTP_201_CREATED,
    response_model=StudentResponse,
    summary="Register a student, issuing their matric number",
    responses=error_responses(401, 403, 409, 422, 500, 503),
)
async def register_new_student(
    body: RegisterNewStudentRequest, principal: security.Department, deps: Deps
) -> StudentResponse:
    """Create the student and issue their matric number in one operation.

    The number is not in the request and cannot be: it is composed from the department's code
    and the entry year, against a counter that survives restarts precisely so two students
    never share one.

    Guarded to a department registrar or the university. There is **no scope check on the
    programme**: it would mean resolving programme → department, which is a cross-context
    lookup this context cannot make (``auth.md`` records the same gap across Admissions). A
    registrar can therefore register a student against another department's programme, and the
    matric number they get would carry that department's code — which is the visible symptom if
    it ever happens.
    """
    student = await deps.register_new_student.execute(
        RegisterNewStudentCommand(**body.model_dump())
    )
    return StudentResponse.of(StudentView.of(student))


@router.get(
    "/students/{student_id}",
    response_model=StudentResponse,
    summary="Read a student",
    responses=error_responses(401, 403, 404, 422, 500, 503),
)
async def read_student(
    student_id: str, principal: security.Authenticated, deps: Deps
) -> StudentResponse:
    """By this context's own identifier — the one every other context references.

    A student reads themselves; a registrar reads anybody. ``require_owner`` matches against
    the token's subject *and* its login id, because a student's login id is their matric number
    and their subject is the ``student_id`` this context minted — a caller may legitimately
    hold either.
    """
    principal.require_owner(student_id)
    student = await deps.read_student.find(student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no student stored with id {student_id!r}",
        )
    return StudentResponse.of(StudentView.of(student))


@router.get(
    "/students",
    response_model=StudentResponse,
    summary="Find a student by matric number or applicant id",
    responses=error_responses(401, 403, 404, 422, 500, 503),
)
async def find_student(
    principal: security.Authenticated,
    deps: Deps,
    matric_number: Annotated[str | None, Query(description="The number on their ID card.")] = None,
    applicant_id: Annotated[
        str | None, Query(description="The id Admissions knew them by.")
    ] = None,
) -> StudentResponse:
    """The other two names a student has.

    ``applicant_id`` is how a client follows a matriculation to the student it produced:
    nothing is published back to Admissions, so the matric number cannot be learned there.

    A matric number that is not a matric number at all is a 404 rather than a 422 — somebody
    typed a number into a lookup box, and "no student with that number" is the honest answer.

    The scope check runs **before** the lookup, against the identifier in the query rather than
    against the student it finds. Checking afterwards would answer 403 for somebody else's
    number and 404 for a number nobody holds, and the difference between those two answers is
    a way to test whether a matric number is real without being allowed to see it.

    One consequence, stated rather than left to be found: a *student* searching by their own
    ``applicant_id`` is refused, because a token carries the student id and the matric number
    and has never heard of an applicant id. Registrars, who are who this lookup is for, are
    unaffected.
    """
    if (matric_number is None) == (applicant_id is None):
        raise HTTPException(
            status_code=422, detail="give exactly one of matric_number or applicant_id"
        )

    principal.require_owner(matric_number, applicant_id)
    student = (
        await deps.read_student.find_by_matric_number(matric_number)
        if matric_number is not None
        else await deps.read_student.find_by_applicant(str(applicant_id))
    )
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="no student matches that identifier"
        )
    return StudentResponse.of(StudentView.of(student))


@router.put(
    "/students/{student_id}/bio-data",
    response_model=StudentResponse,
    summary="Correct a student's bio-data",
    responses=error_responses(401, 403, 404, 422, 500, 503),
)
async def correct_student_bio_data(
    student_id: str,
    body: CorrectStudentBioDataRequest,
    principal: security.Staff,
    deps: Deps,
) -> StudentResponse:
    """Fix what the university got wrong about a person.

    ``PUT`` because it replaces the record rather than patching it, and the matric number does
    not move: it encodes entry year and department, neither of which bio-data touches.

    Unlike a grade correction this demands no reason and no authorizer. A transcript is
    evidence somebody else relies on; a misspelled surname is the university being wrong about
    a person, and making them justify being spelled correctly would be the wrong shape of
    respect.
    """
    student = await deps.correct_student_bio_data.execute(
        CorrectStudentBioDataCommand(student_id=student_id, **body.model_dump())
    )
    return StudentResponse.of(StudentView.of(student))


__all__ = ["STATE_KEY", "StudentProfileDependencies", "router"]
