"""Dict-backed ``StudentRepositoryPort``."""

from student_profile.adapters.outbound._store import InMemoryStore
from student_profile.domain.matric_number import MatricNumber
from student_profile.domain.student import Student
from student_profile.ports.student_repository import StudentRepositoryPort


class InMemoryStudentRepository(StudentRepositoryPort):
    """Holds students in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[Student]("student", lambda student: student.student_id)

    def add(self, student: Student) -> None:
        self._store.add(student)

    def save(self, student: Student) -> None:
        self._store.save(student)

    def get(self, student_id: str) -> Student | None:
        return self._store.get(student_id)

    def find_by_matric_number(self, matric_number: MatricNumber) -> Student | None:
        """A scan, which a unique index does in Phase 6."""
        return next(
            (student for student in self._store.all() if student.matric_number == matric_number),
            None,
        )

    def find_by_applicant(self, applicant_id: str) -> Student | None:
        """A scan. Students registered by hand carry no applicant id and never match."""
        if not applicant_id:
            return None
        return next(
            (student for student in self._store.all() if student.applicant_id == applicant_id),
            None,
        )
