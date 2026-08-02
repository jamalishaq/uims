"""Outbound port for storing and retrieving admission cycles."""

from abc import ABC, abstractmethod

from admissions.domain.admission_cycle import AdmissionCycle


class AdmissionCycleRepositoryPort(ABC):
    """Persistence for the ``AdmissionCycle`` aggregate.

    Keyed by ``(program_id, session_id)``: a cycle *is* one program's intake for one
    session, and last session's cycle stays readable beside this one's. How that pair
    becomes a storage key is the adapter's business, as it is for entry requirements.

    This is the port a quota invariant is ultimately enforced through, and the one place
    an in-memory adapter and a Postgres adapter will differ in kind rather than in
    detail. :meth:`AdmissionCycle.offer` closes the read-check-write gap *within* the
    aggregate; keeping two officers from claiming the same last place across two
    processes is this port's implementation to arrange — row-level locking under
    Postgres, and nothing at all in memory. Nothing above the port learns which.
    """

    @abstractmethod
    def add(self, cycle: AdmissionCycle) -> None:
        """Open a cycle for a program and session.

        Raises:
            DuplicateAggregateError: that program already has a cycle this session.
        """

    @abstractmethod
    def save(self, cycle: AdmissionCycle) -> None:
        """Persist a claimed place, or any other change to a cycle already opened.

        Raises:
            AggregateNotFoundError: no cycle was ever opened for that pair.
        """

    @abstractmethod
    def get(self, program_id: str, session_id: str) -> AdmissionCycle | None:
        """Return the cycle for the program that session, or ``None``.

        ``None`` means nobody opened one, which is not the same as a cycle with a quota
        of zero — that is a program deliberately admitting nobody. The caller decides
        what to make of the difference.
        """
