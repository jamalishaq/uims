"""Open a program's intake for a session: the quota everything else is measured against.

Until this existed a quota could only be set by writing a row into Postgres by hand. That is
worth naming as the gap it was: ``AdmissionCycle`` is the aggregate the whole offer flow turns
on — no cycle for the applied program is the one missing-policy case that *raises* rather than
being skipped — and nothing in the API could create one.

**Owned by the department registrar** (CLAUDE.md section 6). The quota is theirs to set for
their own programs, and it is the number their dashboard reports against.

There is no resize here, and its absence is deliberate rather than forgotten. ``AdmissionCycle``
has no method that changes a quota, because lowering one below ``offers_made`` would either
have to refuse or to un-offer places people are already holding — and which of those a
university wants is a question nobody has answered. Opening is safe; amending is a decision.
"""

from dataclasses import dataclass

from admissions.domain.admission_cycle import AdmissionCycle
from admissions.ports.admission_cycle_repository import AdmissionCycleRepositoryPort


@dataclass(frozen=True)
class OpenAdmissionCycleCommand:
    """One program's intake for one session.

    ``quota`` may be zero, and that is a meaningful thing to say rather than a degenerate
    one: a program not admitting this session has a cycle that is full from the moment it
    opens, which keeps the offer flow from needing a second notion of "closed".
    """

    program_id: str
    session_id: str
    quota: int


class OpenAdmissionCycle:
    """Open a fresh cycle with every place free."""

    def __init__(self, cycles: AdmissionCycleRepositoryPort) -> None:
        self._cycles = cycles

    async def execute(self, command: OpenAdmissionCycleCommand) -> AdmissionCycle:
        """Create the cycle and store it.

        Returns:
            AdmissionCycle: the newly opened cycle, every place free.

        Raises:
            DuplicateAggregateError: a cycle is already open for that program and session.
                Deliberately not an overwrite — a second ``open()`` would reset
                ``offers_made`` to zero and hand out places that are already held.
            InvalidQuotaError: the quota is not a whole, non-negative number of places.
            MissingIdentifierError: the program or session id is blank.
        """
        cycle = AdmissionCycle.open(
            program_id=command.program_id,
            session_id=command.session_id,
            quota=command.quota,
        )
        await self._cycles.add(cycle)
        return cycle
