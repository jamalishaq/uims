"""The ``AddPrerequisite`` use case: load, check, wire, save.

Orchestration only. Two rules apply and this module restates neither: a course cannot
require itself, which :class:`Course` enforces, and a course cannot require something
that already requires it, which :class:`PrerequisiteGraph` enforces. What is left here
is loading the aggregates and deciding that an unresolvable prerequisite id is a
lookup miss rather than a business rejection.

The order matters. The cycle check runs before the aggregate is touched, so a rejected
prerequisite leaves the course exactly as it was — nothing to unwind, and no partial
write to explain.
"""

from dataclasses import dataclass

from course_catalog.application.errors import CourseNotFoundError, PrerequisiteCourseNotFoundError
from course_catalog.domain.course import Course
from course_catalog.domain.prerequisites import PrerequisiteGraph
from course_catalog.ports.course_repository import CourseRepositoryPort


@dataclass(frozen=True)
class AddPrerequisiteCommand:
    """Identifiers only: the use case loads both courses itself."""

    course_id: str
    prerequisite_id: str


class AddPrerequisite:
    """Record that one course must be taken before another."""

    def __init__(self, courses: CourseRepositoryPort) -> None:
        self._courses = courses

    def execute(self, command: AddPrerequisiteCommand) -> Course:
        """Wire the prerequisite in and return the amended course.

        Raises:
            CourseNotFoundError: no such course is stored.
            PrerequisiteCourseNotFoundError: the prerequisite is not in the catalog. A
                course may only require a course this system actually knows about;
                unlike a department id, a prerequisite id is ours to vouch for.
            SelfPrerequisiteError: the course was asked to require itself.
            PrerequisiteCycleError: the prerequisite already requires this course.
            DuplicatePrerequisiteError: this course already requires it.
        """
        course = self._courses.get(command.course_id)
        if course is None:
            raise CourseNotFoundError(f"no course stored with id {command.course_id!r}")

        if self._courses.get(command.prerequisite_id) is None:
            raise PrerequisiteCourseNotFoundError(
                f"no course stored with id {command.prerequisite_id!r}"
            )

        PrerequisiteGraph(self._courses.get).ensure_can_require(course, command.prerequisite_id)

        course.add_prerequisite(command.prerequisite_id)
        self._courses.save(course)
        return course
