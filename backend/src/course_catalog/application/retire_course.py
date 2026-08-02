"""The ``RetireCourse`` use case: withdraw a course from the catalog.

This is the closest thing this context has to a delete, and it deliberately falls
short of one. Enrollment and Academic Records hold ``course_id``s indefinitely — a
transcript from years ago names courses no longer taught — so an id that once resolved
must keep resolving. Retiring says "stop offering this", not "forget this".

Courses that require a retired course are left alone. Whether a curriculum still makes
sense once one of its courses is withdrawn is a question for whoever withdrew it, and
silently rewriting other courses' prerequisites would hide the very thing they need to
see.
"""

from dataclasses import dataclass

from course_catalog.application.errors import CourseNotFoundError
from course_catalog.domain.course import Course
from course_catalog.ports.course_repository import CourseRepositoryPort


@dataclass(frozen=True)
class RetireCourseCommand:
    """Which course to withdraw."""

    course_id: str


class RetireCourse:
    """Withdraw a course from the catalog without forgetting it ever existed."""

    def __init__(self, courses: CourseRepositoryPort) -> None:
        self._courses = courses

    def execute(self, command: RetireCourseCommand) -> Course:
        """Retire the course and return it.

        Retiring an already-retired course is not an error: the caller asked for it to
        be withdrawn, and it is withdrawn.

        Raises:
            CourseNotFoundError: no such course is stored.
        """
        course = self._courses.get(command.course_id)
        if course is None:
            raise CourseNotFoundError(f"no course stored with id {command.course_id!r}")

        course.retire()
        self._courses.save(course)
        return course
