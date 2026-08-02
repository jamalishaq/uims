"""The ``AmendCourse`` use case: correct a stored course's details.

Three things can be amended and one cannot. The code is not amendable, because a
course code is how the rest of the university refers to a course — in a handbook, on a
transcript, in a prerequisite conversation held out loud. Renaming CSC101 to CSC102 is
not a correction, it is a different course, and it should go through ``RegisterCourse``
where the uniqueness check lives.

Every field is optional and ``None`` means "leave this alone", so an adapter that only
wants to fix a typo in the title does not have to resend the credit units and risk
getting them wrong.
"""

from dataclasses import dataclass

from course_catalog.application.errors import CourseNotFoundError
from course_catalog.domain.course import Course
from course_catalog.ports.course_repository import CourseRepositoryPort


@dataclass(frozen=True)
class AmendCourseCommand:
    """Which course to amend, and what about it. ``None`` leaves a field unchanged."""

    course_id: str
    title: str | None = None
    credit_units: int | None = None
    department_id: str | None = None


class AmendCourse:
    """Correct the title, credit units, or offering department of a stored course."""

    def __init__(self, courses: CourseRepositoryPort) -> None:
        self._courses = courses

    def execute(self, command: AmendCourseCommand) -> Course:
        """Apply the amendments and return the course.

        Raises:
            CourseNotFoundError: no such course is stored.
            CourseCatalogError: one of the new values is invalid. Nothing is saved when
                that happens, so a rejected amendment leaves the catalog untouched.
        """
        course = self._courses.get(command.course_id)
        if course is None:
            raise CourseNotFoundError(f"no course stored with id {command.course_id!r}")

        if command.title is not None:
            course.retitle(command.title)
        if command.credit_units is not None:
            course.set_credit_units(command.credit_units)
        if command.department_id is not None:
            course.transfer_to_department(command.department_id)

        self._courses.save(course)
        return course
