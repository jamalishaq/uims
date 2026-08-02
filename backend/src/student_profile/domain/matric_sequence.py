"""The ``MatricSequence`` aggregate: one department's intake counter for one year.

Its single invariant is that **it never hands out the same ordinal twice**. Everything
else about a matric number can be reconstructed; a duplicate cannot be taken back, since
by the time anyone notices, two students are answering to one identifier and every
downstream context — Enrollment, Academic Records, Billing — has already keyed rows on
it.

That invariant has to hold when two students are created at the same moment, which is
exactly what the manual and event paths do. So :meth:`take_next` increments under a lock
rather than leaving read-then-write open to interleaving. The lock is process-local and
therefore only as good as the single-process MVP; under the Postgres adapter of Phase 6
the same guarantee comes from the row itself (``SELECT ... FOR UPDATE`` on the counter),
and the lock here becomes belt-and-braces rather than the whole belt.

The aggregate is the consistency boundary, which is why the counter is an aggregate at
all rather than a field on ``Student`` or a dict inside the issuer: taking a number is a
write to exactly one thing, and it commits before the student that used it is stored.
"""

import threading

from student_profile.domain.errors import InvalidSequenceStateError
from student_profile.domain.values import DepartmentCode, EntryYear

type SequenceKey = tuple[str, int]
"""What identifies a sequence: a department's code and an entry year."""


class MatricSequence:
    """The count of matric numbers issued for one department in one entry year."""

    def __init__(
        self, department_code: DepartmentCode, entry_year: EntryYear, issued: int = 0
    ) -> None:
        if not isinstance(department_code, DepartmentCode):
            raise InvalidSequenceStateError("department_code must be a DepartmentCode")
        if not isinstance(entry_year, EntryYear):
            raise InvalidSequenceStateError("entry_year must be an EntryYear")
        if not isinstance(issued, int) or isinstance(issued, bool) or issued < 0:
            raise InvalidSequenceStateError(f"issued count {issued!r} cannot be negative")
        self._department_code = department_code
        self._entry_year = entry_year
        self._issued = issued
        self._lock = threading.Lock()

    @classmethod
    def start(cls, department_code: DepartmentCode, entry_year: EntryYear) -> "MatricSequence":
        """A department that has admitted nobody yet this year."""
        return cls(department_code, entry_year)

    @classmethod
    def restore(
        cls, department_code: DepartmentCode, entry_year: EntryYear, issued: int
    ) -> "MatricSequence":
        """Rebuild a sequence from stored state. Phase 6's adapter is the caller."""
        return cls(department_code, entry_year, issued)

    @property
    def department_code(self) -> DepartmentCode:
        return self._department_code

    @property
    def entry_year(self) -> EntryYear:
        return self._entry_year

    @property
    def issued(self) -> int:
        """How many numbers this sequence has handed out."""
        return self._issued

    @property
    def key(self) -> SequenceKey:
        return (self._department_code.value, self._entry_year.value)

    def take_next(self) -> int:
        """Claim the next ordinal, permanently.

        There is no way to put one back. A number claimed for a student who then fails to
        be stored is simply burnt, and a gap in the sequence is a far cheaper outcome
        than a reused number.
        """
        with self._lock:
            self._issued += 1
            return self._issued

    def __repr__(self) -> str:
        return (
            f"MatricSequence(department_code={self._department_code.value!r}, "
            f"entry_year={self._entry_year.value}, issued={self._issued})"
        )
