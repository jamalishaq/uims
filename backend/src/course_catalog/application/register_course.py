"""The ``RegisterCourse`` use case: add a course to the catalog.

The only thing this does beyond handing the command to the domain is refuse a code the
catalog already carries. That check cannot live on the entity — no ``Course`` can see
its siblings — so it lives here, in front of the repository that can answer it.
"""

from dataclasses import dataclass

from course_catalog.application.errors import DuplicateCourseCodeError
from course_catalog.domain.course import Course
from course_catalog.ports.course_repository import CourseRepositoryPort


@dataclass(frozen=True)
class RegisterCourseCommand:
    """What an inbound adapter must supply to register one course.

    Prerequisites are not here. A course is registered first and wired into the
    curriculum afterwards, through ``AddPrerequisite`` — which is the only path that
    checks for circularity, and there should be no second way in.
    """

    course_id: str
    department_id: str
    code: str
    title: str
    credit_units: int


class RegisterCourse:
    """Put a new course in the catalog."""

    def __init__(self, courses: CourseRepositoryPort) -> None:
        self._courses = courses

    async def execute(self, command: RegisterCourseCommand) -> Course:
        """Store and return the new course.

        Raises:
            DuplicateCourseCodeError: another course already carries this code.
            DuplicateAggregateError: the course id is already held.
            CourseCatalogError: the code, title, credit units or an identifier is
                invalid. Domain errors pass through untranslated — the domain already
                says exactly what went wrong.
        """
        existing = await self._courses.find_by_code(command.code)
        if existing is not None:
            raise DuplicateCourseCodeError(
                f"course {existing.course_id} already carries code {existing.code!r}"
            )

        course = Course.create(
            command.course_id,
            command.department_id,
            command.code,
            command.title,
            command.credit_units,
        )
        await self._courses.add(course)
        return course
