"""The ``ReadPrerequisiteChain`` use case: what a course really depends on.

The whole of the work belongs to :class:`PrerequisiteGraph`; this loads the course so
that an unknown id is reported as such rather than coming back as an empty chain, and
hands the repository's ``get`` to the graph as its lookup.

Ids are returned rather than courses. The caller most likely to ask this question is
Enrollment, through its own ``CourseInfoPort``, and Enrollment defines its own types for
what comes back (CLAUDE.md section 3) — handing it our aggregates would put this
context's model inside its decisions. Anything that wants the full courses can read
them back through ``ReadCourse``.
"""

from dataclasses import dataclass

from course_catalog.application.errors import CourseNotFoundError
from course_catalog.domain.prerequisites import PrerequisiteGraph
from course_catalog.ports.course_repository import CourseRepositoryPort


@dataclass(frozen=True)
class ReadPrerequisiteChainCommand:
    """Which course to trace back from."""

    course_id: str


class ReadPrerequisiteChain:
    """Read every course required before a given one, directly or not."""

    def __init__(self, courses: CourseRepositoryPort) -> None:
        self._courses = courses

    def execute(self, command: ReadPrerequisiteChainCommand) -> tuple[str, ...]:
        """Return the required course ids, nearest first, each one once.

        Raises:
            CourseNotFoundError: no such course is stored.
        """
        if self._courses.get(command.course_id) is None:
            raise CourseNotFoundError(f"no course stored with id {command.course_id!r}")

        return PrerequisiteGraph(self._courses.get).chain_for(command.course_id)
