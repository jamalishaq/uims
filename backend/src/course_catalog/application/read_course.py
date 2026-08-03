"""The ``ReadCourse`` use case: fetch one course.

A read gets a use case for the same reason a write does — an inbound adapter must not
reach past the port and talk to storage itself (CLAUDE.md section 4), not even for
"just a quick read".

The aggregate is returned as-is rather than flattened into a DTO. Its state is private
and readable only through properties, so there is nothing a caller can do with it that
a DTO would have prevented; a projection would earn its keep once an HTTP adapter needs
a specific shape, and that adapter does not exist yet.
"""

from dataclasses import dataclass

from course_catalog.application.errors import CourseNotFoundError
from course_catalog.domain.course import Course
from course_catalog.ports.course_repository import CourseRepositoryPort


@dataclass(frozen=True)
class ReadCourseCommand:
    """Which course to read."""

    course_id: str


class ReadCourse:
    """Fetch a single course from the catalog."""

    def __init__(self, courses: CourseRepositoryPort) -> None:
        self._courses = courses

    async def execute(self, command: ReadCourseCommand) -> Course:
        """Return the course.

        Absence is an error here, unlike at the port, where ``get`` returns ``None``.
        A caller who names an id is asserting it exists; the port is answering a
        question, and "no" is a valid answer to a question.

        Raises:
            CourseNotFoundError: no such course is stored.
        """
        course = await self._courses.get(command.course_id)
        if course is None:
            raise CourseNotFoundError(f"no course stored with id {command.course_id!r}")
        return course
