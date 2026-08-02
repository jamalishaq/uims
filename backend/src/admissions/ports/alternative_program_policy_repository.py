"""Outbound port for storing and retrieving alternative-program policy."""

from abc import ABC, abstractmethod

from admissions.domain.alternative_program_policy import AlternativeProgramPolicy


class AlternativeProgramPolicyRepositoryPort(ABC):
    """Persistence for the ``AlternativeProgramPolicy`` policy data.

    Keyed by ``(program_id, session_id)`` for the reason entry requirements are: the
    policy is session-scoped, and which programs Computer Science overflowed into in 2026
    is not overwritten by where it overflows in 2027. An applicant offered an alternative
    was offered it under the chain in force then, and the record has to be able to say so.
    """

    @abstractmethod
    def add(self, policy: AlternativeProgramPolicy) -> None:
        """Publish a fallback chain for a program and session.

        Raises:
            DuplicateAggregateError: that program already has a policy this session.
        """

    @abstractmethod
    def save(self, policy: AlternativeProgramPolicy) -> None:
        """Persist a change to a policy already published.

        Raises:
            AggregateNotFoundError: no policy was ever published for that pair.
        """

    @abstractmethod
    def get(self, program_id: str, session_id: str) -> AlternativeProgramPolicy | None:
        """Return the fallback chain for the program that session, or ``None``.

        ``None`` means nobody published one. It is deliberately indistinguishable in
        effect from a published chain that is empty: either way the program has nowhere
        to overflow to, and an applicant it cannot seat is told no offer is available.
        """
