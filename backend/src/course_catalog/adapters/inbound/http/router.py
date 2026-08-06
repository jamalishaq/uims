"""HTTP routes for Course Catalog: reference-data CRUD and prerequisite chains.

Every route here does the same three things and nothing else — build a command from the
request, await a use case, project the answer through ``CourseView``. No route decides
anything: whether a course may require itself, whether a chain would cycle, whether a code is
already taken are all the domain's and the application layer's judgements, and they arrive here
as exceptions that ``errors.py`` maps to statuses.

The dependencies arrive on ``app.state`` rather than by importing the composition root, which
would be a cycle — the root imports this module to mount it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

import security
from course_catalog.adapters.inbound.http.schemas import (
    AmendCourseRequest,
    CourseListResponse,
    CourseResponse,
    PrerequisiteChainResponse,
    RegisterCourseRequest,
)
from course_catalog.application.add_prerequisite import AddPrerequisite, AddPrerequisiteCommand
from course_catalog.application.amend_course import AmendCourse, AmendCourseCommand
from course_catalog.application.list_department_courses import (
    ListDepartmentCourses,
    ListDepartmentCoursesCommand,
)
from course_catalog.application.read_course import ReadCourse, ReadCourseCommand
from course_catalog.application.read_prerequisite_chain import (
    ReadPrerequisiteChain,
    ReadPrerequisiteChainCommand,
)
from course_catalog.application.register_course import RegisterCourse, RegisterCourseCommand
from course_catalog.application.reinstate_course import ReinstateCourse, ReinstateCourseCommand
from course_catalog.application.remove_prerequisite import (
    RemovePrerequisite,
    RemovePrerequisiteCommand,
)
from course_catalog.application.retire_course import RetireCourse, RetireCourseCommand
from course_catalog.application.views import CourseView
from http_api import dependencies_of, error_responses

STATE_KEY = "course_catalog"
"""Where this context's use cases hang on ``app.state``. Owned here, read by the root."""


class CourseCatalogDependencies:
    """The use cases this router needs, wired once at startup."""

    def __init__(
        self,
        register_course: RegisterCourse,
        amend_course: AmendCourse,
        read_course: ReadCourse,
        list_department_courses: ListDepartmentCourses,
        retire_course: RetireCourse,
        reinstate_course: ReinstateCourse,
        add_prerequisite: AddPrerequisite,
        remove_prerequisite: RemovePrerequisite,
        read_prerequisite_chain: ReadPrerequisiteChain,
    ) -> None:
        self.register_course = register_course
        self.amend_course = amend_course
        self.read_course = read_course
        self.list_department_courses = list_department_courses
        self.retire_course = retire_course
        self.reinstate_course = reinstate_course
        self.add_prerequisite = add_prerequisite
        self.remove_prerequisite = remove_prerequisite
        self.read_prerequisite_chain = read_prerequisite_chain


def _deps(request: Request) -> CourseCatalogDependencies:
    return dependencies_of(request, STATE_KEY, CourseCatalogDependencies)


Deps = Annotated[CourseCatalogDependencies, Depends(_deps)]

router = APIRouter(prefix="/course-catalog", tags=["course-catalog"])


@router.post(
    "/courses",
    status_code=status.HTTP_201_CREATED,
    response_model=CourseResponse,
    summary="Register a course",
    responses=error_responses(401, 403, 409, 422, 500, 503),
)
async def register_course(
    body: RegisterCourseRequest, principal: security.Department, deps: Deps
) -> CourseResponse:
    course = await deps.register_course.execute(RegisterCourseCommand(**body.model_dump()))
    return CourseResponse.of(CourseView.of(course))


@router.get(
    "/courses/{course_id}",
    response_model=CourseResponse,
    summary="Read a course",
    responses=error_responses(401, 404, 422, 500, 503),
)
async def read_course(
    course_id: str, principal: security.Authenticated, deps: Deps
) -> CourseResponse:
    course = await deps.read_course.execute(ReadCourseCommand(course_id=course_id))
    return CourseResponse.of(CourseView.of(course))


@router.patch(
    "/courses/{course_id}",
    response_model=CourseResponse,
    summary="Amend a course",
    responses=error_responses(401, 403, 404, 422, 500, 503),
)
async def amend_course(
    course_id: str,
    body: AmendCourseRequest,
    principal: security.Department,
    deps: Deps,
) -> CourseResponse:
    course = await deps.amend_course.execute(
        AmendCourseCommand(course_id=course_id, **body.model_dump())
    )
    return CourseResponse.of(CourseView.of(course))


@router.post(
    "/courses/{course_id}/retirement",
    response_model=CourseResponse,
    summary="Retire a course",
    responses=error_responses(401, 403, 404, 422, 500, 503),
)
async def retire_course(
    course_id: str, principal: security.Department, deps: Deps
) -> CourseResponse:
    """Retire a course. Retired courses stay readable — transcripts refer to them forever."""
    course = await deps.retire_course.execute(RetireCourseCommand(course_id=course_id))
    return CourseResponse.of(CourseView.of(course))


@router.delete(
    "/courses/{course_id}/retirement",
    response_model=CourseResponse,
    summary="Reinstate a retired course",
    responses=error_responses(401, 403, 404, 422, 500, 503),
)
async def reinstate_course(
    course_id: str, principal: security.Department, deps: Deps
) -> CourseResponse:
    course = await deps.reinstate_course.execute(ReinstateCourseCommand(course_id=course_id))
    return CourseResponse.of(CourseView.of(course))


@router.get(
    "/departments/{department_id}/courses",
    response_model=CourseListResponse,
    summary="List a department's courses",
    responses=error_responses(401, 422, 500, 503),
)
async def list_department_courses(
    department_id: str,
    principal: security.Authenticated,
    deps: Deps,
    include_retired: Annotated[bool, Query(description="Include retired courses.")] = False,
) -> CourseListResponse:
    """A department nobody has is an empty list, not a 404 — the use case raises nothing."""
    courses = await deps.list_department_courses.execute(
        ListDepartmentCoursesCommand(department_id=department_id, include_retired=include_retired)
    )
    return CourseListResponse(
        courses=tuple(CourseResponse.of(view) for view in CourseView.of_each(courses))
    )


@router.put(
    "/courses/{course_id}/prerequisites/{prerequisite_id}",
    response_model=CourseResponse,
    summary="Add a prerequisite",
    responses=error_responses(401, 403, 404, 409, 422, 500, 503),
)
async def add_prerequisite(
    course_id: str, prerequisite_id: str, principal: security.Department, deps: Deps
) -> CourseResponse:
    """``PUT`` because it is idempotent in intent; a repeat is a 409 from the domain."""
    course = await deps.add_prerequisite.execute(
        AddPrerequisiteCommand(course_id=course_id, prerequisite_id=prerequisite_id)
    )
    return CourseResponse.of(CourseView.of(course))


@router.delete(
    "/courses/{course_id}/prerequisites/{prerequisite_id}",
    response_model=CourseResponse,
    summary="Remove a prerequisite",
    responses=error_responses(401, 403, 404, 409, 422, 500, 503),
)
async def remove_prerequisite(
    course_id: str,
    prerequisite_id: str,
    principal: security.Department,
    deps: Deps,
) -> CourseResponse:
    course = await deps.remove_prerequisite.execute(
        RemovePrerequisiteCommand(course_id=course_id, prerequisite_id=prerequisite_id)
    )
    return CourseResponse.of(CourseView.of(course))


@router.get(
    "/courses/{course_id}/prerequisite-chain",
    response_model=PrerequisiteChainResponse,
    summary="Read a course's full prerequisite chain",
    responses=error_responses(401, 404, 422, 500, 503),
)
async def read_prerequisite_chain(
    course_id: str, principal: security.Authenticated, deps: Deps
) -> PrerequisiteChainResponse:
    """Every course that must be passed first, transitively — not just the direct ones."""
    chain = await deps.read_prerequisite_chain.execute(
        ReadPrerequisiteChainCommand(course_id=course_id)
    )
    return PrerequisiteChainResponse(course_id=course_id, prerequisite_ids=chain)


__all__ = ["STATE_KEY", "CourseCatalogDependencies", "router"]
