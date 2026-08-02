"""Dict-backed ``AlternativeProgramPolicyRepositoryPort``."""

from admissions.adapters.outbound._store import InMemoryStore
from admissions.domain.alternative_program_policy import AlternativeProgramPolicy
from admissions.ports.alternative_program_policy_repository import (
    AlternativeProgramPolicyRepositoryPort,
)


def _key(program_id: str, session_id: str) -> str:
    """Flatten the port's composite key into the one string a dict can hold.

    The separator is not a character an identifier may contain, so two different pairs
    cannot flatten to the same key. This translation is the adapter's alone.
    """
    return f"{program_id}\x00{session_id}"


class InMemoryAlternativeProgramPolicyRepository(AlternativeProgramPolicyRepositoryPort):
    """Holds alternative-program policy in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[AlternativeProgramPolicy](
            "alternative program policy",
            lambda policy: _key(policy.program_id, policy.session_id),
        )

    def add(self, policy: AlternativeProgramPolicy) -> None:
        self._store.add(policy)

    def save(self, policy: AlternativeProgramPolicy) -> None:
        self._store.save(policy)

    def get(self, program_id: str, session_id: str) -> AlternativeProgramPolicy | None:
        return self._store.get(_key(program_id, session_id))
