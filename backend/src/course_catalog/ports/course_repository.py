"""Outbound port for storing and retrieving courses."""

from abc import ABC, abstractmethod

from course_catalog.domain.course import Course


class CourseRepositoryPort(ABC):
    """Persistence for the ``Course`` aggregate.

    There is no ``remove``. Courses are retired, not deleted: Enrollment and Academic
    Records hold ``course_id``s indefinitely, so an id that once resolved must keep
    resolving. A repository that could make a course vanish would be a repository that
    could strand a transcript.
    """

    @abstractmethod
    def add(self, course: Course) -> None:
        """Store a new course.

        Raises:
            DuplicateAggregateError: the course id is already held.
        """

    @abstractmethod
    def save(self, course: Course) -> None:
        """Persist changes to a course that is already stored.

        Raises:
            AggregateNotFoundError: the course id was never added.
        """

    @abstractmethod
    def get(self, course_id: str) -> Course | None:
        """Return the course, or ``None`` if no such id is held."""

    @abstractmethod
    def list_all(self) -> tuple[Course, ...]:
        """Every course in the catalog, in the order it was added."""

    @abstractmethod
    def list_for_department(self, department_id: str) -> tuple[Course, ...]:
        """Every course offered by one department, in the order it was added."""

    @abstractmethod
    def find_by_code(self, code: str) -> Course | None:
        """Return the course carrying this code, or ``None``.

        Matching is case-insensitive, because storage is: codes are normalised on the
        way in, and a lookup that did not normalise the same way would report a code as
        free when it is taken.
        """
