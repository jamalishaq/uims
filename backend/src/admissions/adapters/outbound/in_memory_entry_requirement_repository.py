"""Dict-backed ``ProgramEntryRequirementRepositoryPort``."""

from admissions.adapters.outbound._store import InMemoryStore
from admissions.domain.entry_requirement import ProgramEntryRequirement
from admissions.ports.entry_requirement_repository import ProgramEntryRequirementRepositoryPort


def _key(program_id: str, session_id: str) -> str:
    """Flatten the port's composite key into the one string a dict can hold.

    The separator is not a character an identifier may contain, so two different pairs
    cannot flatten to the same key. This translation is the adapter's alone: under
    Postgres the same pair becomes two columns and a composite primary key, and neither
    the domain type nor the use cases learn that anything changed.
    """
    return f"{program_id}\x00{session_id}"


class InMemoryProgramEntryRequirementRepository(ProgramEntryRequirementRepositoryPort):
    """Holds entry requirements in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[ProgramEntryRequirement](
            "entry requirement",
            lambda requirement: _key(requirement.program_id, requirement.session_id),
        )

    async def add(self, requirement: ProgramEntryRequirement) -> None:
        self._store.add(requirement)

    async def save(self, requirement: ProgramEntryRequirement) -> None:
        self._store.save(requirement)

    async def get(self, program_id: str, session_id: str) -> ProgramEntryRequirement | None:
        return self._store.get(_key(program_id, session_id))
