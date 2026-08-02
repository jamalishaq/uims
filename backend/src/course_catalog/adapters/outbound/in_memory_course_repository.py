"""Dict-backed ``CourseRepositoryPort``."""

from course_catalog.adapters.outbound._store import InMemoryStore
from course_catalog.domain.course import Course
from course_catalog.domain.values import require_code
from course_catalog.ports.course_repository import CourseRepositoryPort


class InMemoryCourseRepository(CourseRepositoryPort):
    """Holds courses in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[Course]("course", lambda course: course.course_id)

    def add(self, course: Course) -> None:
        self._store.add(course)

    def save(self, course: Course) -> None:
        self._store.save(course)

    def get(self, course_id: str) -> Course | None:
        return self._store.get(course_id)

    def list_all(self) -> tuple[Course, ...]:
        return self._store.all()

    def list_for_department(self, department_id: str) -> tuple[Course, ...]:
        return tuple(
            course for course in self._store.all() if course.department_id == department_id
        )

    def find_by_code(self, code: str) -> Course | None:
        """Normalises the argument the same way ``Course`` normalises the stored code.

        Without that, ``find_by_code("csc101")`` would miss a stored ``CSC101`` and
        report the code as free when it is taken.
        """
        wanted = require_code(code, "course code")
        return next((course for course in self._store.all() if course.code == wanted), None)
