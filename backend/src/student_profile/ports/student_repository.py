"""Outbound port for storing and retrieving students."""

from abc import ABC, abstractmethod

from student_profile.domain.matric_number import MatricNumber
from student_profile.domain.student import Student


class StudentRepositoryPort(ABC):
    """Persistence for the ``Student`` aggregate."""

    @abstractmethod
    def add(self, student: Student) -> None:
        """Store a new student.

        Raises:
            DuplicateAggregateError: the student id is already held.
        """

    @abstractmethod
    def save(self, student: Student) -> None:
        """Persist changes to a student who is already stored.

        Raises:
            AggregateNotFoundError: the student id was never added.
        """

    @abstractmethod
    def get(self, student_id: str) -> Student | None:
        """Return the student, or ``None`` if no such id is held."""

    @abstractmethod
    def find_by_matric_number(self, matric_number: MatricNumber) -> Student | None:
        """Return the student holding this matric number, or ``None``.

        The lookup every other context ultimately needs: a matric number is what a
        registrar, a bursar and a student all quote, and it is not the storage key.
        """

    @abstractmethod
    def find_by_applicant(self, applicant_id: str) -> Student | None:
        """Return the student matriculated from this applicant, or ``None``.

        This is what makes consuming ``StudentMatriculated`` idempotent. Event delivery
        retries; without this the second delivery would issue a second matric number to
        somebody who already has one.
        """
