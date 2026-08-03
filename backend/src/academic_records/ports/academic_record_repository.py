"""Outbound port for storing and retrieving academic records."""

from abc import ABC, abstractmethod

from academic_records.domain.academic_record import AcademicRecord


class AcademicRecordRepositoryPort(ABC):
    """Persistence for the ``AcademicRecord`` aggregate, keyed by ``student_id``.

    Keyed by the student and not by a surrogate id of its own, because there is exactly one
    record per student and the aggregate is only ever reached by asking about a person. A
    second key would be a second thing to look a record up by and a second thing to get
    wrong.

    There is no ``remove``, for a stronger version of the reason ``EnrollmentRepositoryPort``
    gives: a transcript is the university's permanent statement about what somebody
    achieved, and is asked for by employers and other institutions decades after the
    student leaves. Nothing in this system deletes one.
    """

    @abstractmethod
    async def add(self, record: AcademicRecord) -> None:
        """Store a record for a student who did not have one.

        Raises:
            DuplicateAggregateError: a record is already held for that student.
        """

    @abstractmethod
    async def save(self, record: AcademicRecord) -> None:
        """Persist changes to a record that is already stored.

        Raises:
            AggregateNotFoundError: no record was ever added for that student.
        """

    @abstractmethod
    async def get(self, student_id: str) -> AcademicRecord | None:
        """Return the student's record, or ``None`` if nobody has graded them yet.

        ``None`` is an answer and not a failure, and it is the answer for every student
        until their first mark is submitted.
        """
