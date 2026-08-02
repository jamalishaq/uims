"""Outbound port for the per-department/year matric sequences."""

from abc import ABC, abstractmethod

from student_profile.domain.matric_sequence import MatricSequence
from student_profile.domain.values import DepartmentCode, EntryYear


class MatricSequenceRepositoryPort(ABC):
    """Persistence for the ``MatricSequence`` aggregate."""

    @abstractmethod
    def get_or_start(
        self, department_code: DepartmentCode, entry_year: EntryYear
    ) -> MatricSequence:
        """Return the sequence for this department and year, starting one if there is none.

        Get-or-create is one operation, not two, because it has to be atomic: two callers
        racing on a department's first student of the year must receive *the same*
        sequence, or both will be handed ordinal 1 and two students will hold one matric
        number. Implementations must serialise this; the in-memory adapter takes a lock,
        and Phase 6's Postgres adapter gets it from an upsert.

        There is no ``add``. A sequence is never created deliberately by anyone — it comes
        into existence because a department admitted somebody — so there is no caller who
        could get the ordering of add-then-read right.
        """

    @abstractmethod
    def save(self, sequence: MatricSequence) -> None:
        """Persist a sequence whose counter has moved.

        Must be called before the student that used the number is stored. If the process
        dies in between, the sequence has a gap and the student does not exist; the other
        order would leave a live student whose number the counter will hand out again.
        """

    @abstractmethod
    def get(self, department_code: DepartmentCode, entry_year: EntryYear) -> MatricSequence | None:
        """Return the sequence, or ``None`` if this department has admitted nobody that year.

        Read-only, for reporting on an intake. Issuance uses :meth:`get_or_start`.
        """
