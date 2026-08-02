"""The ``RemovePrerequisite`` use case: unwire one prerequisite.

No graph check here. Removing an edge cannot create a cycle, and a chain that gets
shorter cannot become circular — the asymmetry with ``AddPrerequisite`` is the point,
not an omission.

The prerequisite course itself is not loaded. A course may hold the id of something
that has since been retired, and refusing to let go of a prerequisite because the
prerequisite is in a bad state would be exactly backwards.
"""

from dataclasses import dataclass

from course_catalog.application.errors import CourseNotFoundError
from course_catalog.domain.course import Course
from course_catalog.ports.course_repository import CourseRepositoryPort


@dataclass(frozen=True)
class RemovePrerequisiteCommand:
    """Which course to amend, and which prerequisite to drop."""

    course_id: str
    prerequisite_id: str


class RemovePrerequisite:
    """Stop requiring one course before another."""

    def __init__(self, courses: CourseRepositoryPort) -> None:
        self._courses = courses

    def execute(self, command: RemovePrerequisiteCommand) -> Course:
        """Drop the prerequisite and return the amended course.

        Raises:
            CourseNotFoundError: no such course is stored.
            PrerequisiteNotRequiredError: the course does not require it.
        """
        course = self._courses.get(command.course_id)
        if course is None:
            raise CourseNotFoundError(f"no course stored with id {command.course_id!r}")

        course.remove_prerequisite(command.prerequisite_id)
        self._courses.save(course)
        return course
