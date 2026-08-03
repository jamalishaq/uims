"""Dict-backed ``EnrollmentRepositoryPort``."""

from enrollment.adapters.outbound._store import InMemoryStore
from enrollment.domain.enrollment import Enrollment
from enrollment.domain.values import Term
from enrollment.ports.enrollment_repository import EnrollmentRepositoryPort


class InMemoryEnrollmentRepository(EnrollmentRepositoryPort):
    """Holds registrations in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[Enrollment](
            "enrollment", lambda enrollment: enrollment.enrollment_id
        )

    def add(self, enrollment: Enrollment) -> None:
        self._store.add(enrollment)

    def save(self, enrollment: Enrollment) -> None:
        self._store.save(enrollment)

    def get(self, enrollment_id: str) -> Enrollment | None:
        return self._store.get(enrollment_id)

    def list_for_student_in_term(self, student_id: str, term: Term) -> tuple[Enrollment, ...]:
        return tuple(
            enrollment
            for enrollment in self._store.all()
            if enrollment.student_id == student_id and enrollment.term == term
        )

    def has_registered_before(self, student_id: str, course_id: str) -> bool:
        return any(
            enrollment.student_id == student_id and enrollment.course_id == course_id
            for enrollment in self._store.all()
        )
