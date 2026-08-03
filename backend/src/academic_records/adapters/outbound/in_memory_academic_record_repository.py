"""Dict-backed ``AcademicRecordRepositoryPort``, keyed by ``student_id``."""

from academic_records.adapters.outbound._store import InMemoryStore
from academic_records.domain.academic_record import AcademicRecord
from academic_records.ports.academic_record_repository import AcademicRecordRepositoryPort


class InMemoryAcademicRecordRepository(AcademicRecordRepositoryPort):
    """Holds academic records in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[AcademicRecord](
            "academic record", lambda record: record.student_id
        )

    def add(self, record: AcademicRecord) -> None:
        self._store.add(record)

    def save(self, record: AcademicRecord) -> None:
        self._store.save(record)

    def get(self, student_id: str) -> AcademicRecord | None:
        return self._store.get(student_id)
