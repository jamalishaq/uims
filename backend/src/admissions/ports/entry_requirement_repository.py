"""Outbound port for storing and retrieving program entry requirements."""

from abc import ABC, abstractmethod

from admissions.domain.entry_requirement import ProgramEntryRequirement


class ProgramEntryRequirementRepositoryPort(ABC):
    """Persistence for the ``ProgramEntryRequirement`` policy data.

    Keyed by ``(program_id, session_id)``, not by program alone, because the policy is
    session-scoped (CLAUDE.md section 3). Publishing this session's requirement must not
    overwrite last session's: an applicant screened a year ago was screened against the
    rule in force then, and the record has to be able to say so.

    How that pair becomes a storage key is the adapter's business and stops there — the
    domain type carries two fields, not a composite id somebody has to keep in step.
    """

    @abstractmethod
    async def add(self, requirement: ProgramEntryRequirement) -> None:
        """Publish a requirement for a program and session.

        Raises:
            DuplicateAggregateError: that program already has a requirement this session.
        """

    @abstractmethod
    async def save(self, requirement: ProgramEntryRequirement) -> None:
        """Persist a change to a requirement already published.

        Raises:
            AggregateNotFoundError: no requirement was ever published for that pair.
        """

    @abstractmethod
    async def get(self, program_id: str, session_id: str) -> ProgramEntryRequirement | None:
        """Return the requirement in force for the program that session, or ``None``.

        ``None`` means nobody has published one, which is not the same as a requirement
        that demands nothing — the caller decides what to make of the difference.
        """
