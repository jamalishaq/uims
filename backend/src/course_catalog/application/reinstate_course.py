"""The ``ReinstateCourse`` use case: bring a retired course back.

The counterpart to ``RetireCourse``, and the reason retiring is safe to do: a course
withdrawn by mistake, or revived after a few years out of the handbook, comes back with
its code, its credit units and its prerequisites intact, under the same id every other
context already holds.
"""

from dataclasses import dataclass

from course_catalog.application.errors import CourseNotFoundError
from course_catalog.domain.course import Course
from course_catalog.ports.course_repository import CourseRepositoryPort


@dataclass(frozen=True)
class ReinstateCourseCommand:
    """Which course to bring back."""

    course_id: str


class ReinstateCourse:
    """Return a retired course to the catalog."""

    def __init__(self, courses: CourseRepositoryPort) -> None:
        self._courses = courses

    def execute(self, command: ReinstateCourseCommand) -> Course:
        """Reinstate the course and return it.

        Raises:
            CourseNotFoundError: no such course is stored.
        """
        course = self._courses.get(command.course_id)
        if course is None:
            raise CourseNotFoundError(f"no course stored with id {command.course_id!r}")

        course.reinstate()
        self._courses.save(course)
        return course
