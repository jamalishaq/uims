"""Dict-backed ``CourseOfferingRepositoryPort``."""

from enrollment.adapters.outbound._store import InMemoryStore
from enrollment.domain.course_offering import CourseOffering
from enrollment.domain.values import Term
from enrollment.ports.course_offering_repository import CourseOfferingRepositoryPort


def _key(course_id: str, term: Term) -> str:
    """The offering's identity as one string: the same course next term is a different one."""
    return f"{course_id}|{term.session_id}|{term.semester_id}"


class InMemoryCourseOfferingRepository(CourseOfferingRepositoryPort):
    """Holds offerings in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[CourseOffering](
            "course offering", lambda offering: _key(offering.course_id, offering.term)
        )

    def add(self, offering: CourseOffering) -> None:
        self._store.add(offering)

    def save(self, offering: CourseOffering) -> None:
        self._store.save(offering)

    def get(self, course_id: str, term: Term) -> CourseOffering | None:
        return self._store.get(_key(course_id, term))
