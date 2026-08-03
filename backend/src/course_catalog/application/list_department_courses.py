"""The ``ListDepartmentCourses`` use case: everything one department offers.

Retired courses are excluded by default, because the common reason to ask this
question is "what can be taken" and a handbook full of withdrawn courses answers a
different one. ``include_retired`` is there for the administrative view, which needs to
see them precisely in order to reinstate one.

A department that offers nothing — or does not exist, which from here looks the same —
gets an empty tuple. This context cannot tell the two apart: ``department_id`` belongs
to Faculty & Department and is opaque to us, and asking them would mean a query port
that CLAUDE.md section 3 does not give this context.
"""

from dataclasses import dataclass

from course_catalog.domain.course import Course
from course_catalog.ports.course_repository import CourseRepositoryPort


@dataclass(frozen=True)
class ListDepartmentCoursesCommand:
    """Which department's courses to list, and whether retired ones count."""

    department_id: str
    include_retired: bool = False


class ListDepartmentCourses:
    """List the courses offered by one department."""

    def __init__(self, courses: CourseRepositoryPort) -> None:
        self._courses = courses

    async def execute(self, command: ListDepartmentCoursesCommand) -> tuple[Course, ...]:
        """Return the department's courses, in the order they were added."""
        courses = await self._courses.list_for_department(command.department_id)
        if command.include_retired:
            return courses
        return tuple(course for course in courses if course.is_active)
