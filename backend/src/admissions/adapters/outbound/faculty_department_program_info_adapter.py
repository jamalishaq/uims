"""The real adapter behind ``ProgramInfoPort``: is this program real, and is it admitting?

Fed rather than reading Faculty & Department directly — rule (b), the
``BillingFinancialClearanceAdapter`` pattern. The composition root calls
``ReadProgramPlacement`` and hands back the three fields below.

**This is where the session dimension is reconciled**, which is exactly what the port's docstring
promises: "Faculty & Department holds ``is_admitting`` as a flag on the program itself with no
session dimension; reconciling that with a question asked per session is the adapter's work."

The reconciliation, stated: a program is admitting *for a session* when the program's own flag is
set **and** that session is open. A closed session is not a session anybody may apply into, and a
program flagged as admitting says nothing about which session it is admitting into — the flag
alone would let an application be filed against a session that closed last year. Requiring both
is the narrower reading, and it fails in the safe direction: an applicant is told the program is
not admitting rather than being admitted into a session that has ended.

If admissions windows ever become genuinely per-session over there, this file changes and the
port does not.

**A program nobody has is ``None``; a program that exists and is closed is not.** The port's
docstring is explicit that the application layer makes something of the difference —
``ProgramNotFoundError`` against ``ProgramNotAdmittingError`` — so collapsing the two here would
turn a real program's closed window into "no such program".
"""

from dataclasses import dataclass
from typing import Protocol

from admissions.ports.program_info import ProgramInfo, ProgramInfoPort


@dataclass(frozen=True)
class ProgramPlacement:
    """What Faculty & Department has to say about a program and a session, in primitives."""

    program_id: str
    is_admitting: bool
    session_is_open: bool


class ProgramPlacementSource(Protocol):
    """Whatever can say where a program sits and whether its session is open."""

    async def program_placement(self, program_id: str, session_id: str) -> ProgramPlacement | None:
        """The placement, or ``None`` if the program or the session is not known there."""
        ...


class FacultyDepartmentProgramInfoAdapter(ProgramInfoPort):
    """Reads Faculty & Department through a source, and answers in ``ProgramInfo``."""

    def __init__(self, source: ProgramPlacementSource) -> None:
        self._source = source

    async def program_for(self, program_id: str, session_id: str) -> ProgramInfo | None:
        """What is known about the program for that session, or ``None`` if it is not known."""
        placement = await self._source.program_placement(program_id, session_id)
        if placement is None:
            return None
        return ProgramInfo(
            program_id=placement.program_id,
            is_admitting=placement.is_admitting and placement.session_is_open,
        )
