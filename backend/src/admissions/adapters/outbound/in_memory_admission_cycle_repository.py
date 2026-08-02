"""Dict-backed ``AdmissionCycleRepositoryPort``."""

from admissions.adapters.outbound._store import InMemoryStore
from admissions.domain.admission_cycle import AdmissionCycle
from admissions.ports.admission_cycle_repository import AdmissionCycleRepositoryPort


def _key(program_id: str, session_id: str) -> str:
    """Flatten the port's composite key into the one string a dict can hold.

    The separator is not a character an identifier may contain, so two different pairs
    cannot flatten to the same key. Under Postgres the same pair becomes two columns and a
    composite primary key, and nothing above this file learns that anything changed.
    """
    return f"{program_id}\x00{session_id}"


class InMemoryAdmissionCycleRepository(AdmissionCycleRepositoryPort):
    """Holds admission cycles in memory for the duration of the process.

    Single-process and unlocked, which is the honest limit of this adapter rather than a
    bug in it: the quota invariant holds because :meth:`AdmissionCycle.offer` checks and
    increments in one operation, and two *threads* interleaving between that call and
    ``save`` is a race a real database's row lock closes. Phase 6's adapter is where that
    lock lives.
    """

    def __init__(self) -> None:
        self._store = InMemoryStore[AdmissionCycle](
            "admission cycle",
            lambda cycle: _key(cycle.program_id, cycle.session_id),
        )

    def add(self, cycle: AdmissionCycle) -> None:
        self._store.add(cycle)

    def save(self, cycle: AdmissionCycle) -> None:
        self._store.save(cycle)

    def get(self, program_id: str, session_id: str) -> AdmissionCycle | None:
        return self._store.get(_key(program_id, session_id))
