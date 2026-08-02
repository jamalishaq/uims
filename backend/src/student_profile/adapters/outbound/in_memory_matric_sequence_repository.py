"""Dict-backed ``MatricSequenceRepositoryPort``.

Not built on :class:`InMemoryStore`, unlike the student repository. The store's ``add``
raises on a key it already holds, which is precisely the race this adapter has to absorb:
two threads reaching a department's first student of the year must both come away with
the *same* sequence. So the mapping is held directly and get-or-create happens under a
lock.

The lock and the store's "live references" behaviour together make issuance safe in this
process: callers share one ``MatricSequence`` object, and that object serialises its own
counter. Phase 6 replaces both mechanisms at once — the row is the shared state and
``SELECT ... FOR UPDATE`` is the lock — and nothing above this adapter changes.
"""

import threading

from student_profile.domain.matric_sequence import MatricSequence, SequenceKey
from student_profile.domain.values import DepartmentCode, EntryYear
from student_profile.ports.errors import AggregateNotFoundError
from student_profile.ports.matric_sequence_repository import MatricSequenceRepositoryPort


class InMemoryMatricSequenceRepository(MatricSequenceRepositoryPort):
    """Holds the per-department/year counters in memory for the life of the process."""

    def __init__(self) -> None:
        self._sequences: dict[SequenceKey, MatricSequence] = {}
        self._lock = threading.Lock()

    def get_or_start(
        self, department_code: DepartmentCode, entry_year: EntryYear
    ) -> MatricSequence:
        key = (department_code.value, entry_year.value)
        with self._lock:
            sequence = self._sequences.get(key)
            if sequence is None:
                sequence = MatricSequence.start(department_code, entry_year)
                self._sequences[key] = sequence
            return sequence

    def save(self, sequence: MatricSequence) -> None:
        with self._lock:
            if sequence.key not in self._sequences:
                raise AggregateNotFoundError(f"matric sequence {sequence.key} was never started")
            self._sequences[sequence.key] = sequence

    def get(self, department_code: DepartmentCode, entry_year: EntryYear) -> MatricSequence | None:
        with self._lock:
            return self._sequences.get((department_code.value, entry_year.value))

    def all(self) -> tuple[MatricSequence, ...]:
        """Every sequence started so far. Not on the port: for tests and reporting."""
        with self._lock:
            return tuple(self._sequences.values())
