"""Outbound port for storing and retrieving applicants."""

from abc import ABC, abstractmethod

from admissions.domain.applicant import Applicant


class ApplicantRepositoryPort(ABC):
    """Persistence for the ``Applicant`` aggregate.

    There is no ``remove``. An application that reached an outcome is the university's
    record of what it decided and when, and an applicant who was turned away this session
    may apply again the next — a repository that could make an application vanish would be
    a repository that could lose the only evidence a decision was ever made.
    """

    @abstractmethod
    def add(self, applicant: Applicant) -> None:
        """Store a new application.

        Raises:
            DuplicateAggregateError: the applicant id is already held.
        """

    @abstractmethod
    def save(self, applicant: Applicant) -> None:
        """Persist changes to an application that is already stored.

        Raises:
            AggregateNotFoundError: the applicant id was never added.
        """

    @abstractmethod
    def get(self, applicant_id: str) -> Applicant | None:
        """Return the applicant, or ``None`` if no such id is held."""

    @abstractmethod
    def list_for_session(self, session_id: str) -> tuple[Applicant, ...]:
        """Every application made for one session, in the order it was added.

        Session-scoped rather than wholesale: admissions work is done a session at a time,
        and a list spanning every session anyone ever applied in is not a list anybody in
        this context has a use for.
        """
