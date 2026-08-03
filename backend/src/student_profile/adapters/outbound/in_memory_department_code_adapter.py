"""The anti-corruption adapter behind ``DepartmentCodePort``.

This is where Faculty & Department's model would be translated into ours — and the
reason it is *fed* data rather than reading that context directly is the dependency rule
itself: no module may import another context at any layer, adapters included (CLAUDE.md
section 4, rule (b) of the architecture fitness test). Whatever sits on the other side of
this port is reached over a boundary that is not a Python import: in Phase 6 that is
Faculty & Department's read-model or API, and this class is replaced by one that speaks
to it.

Two translations live here, and only here:

* **Alphabetic to numeric department code.** Faculty & Department holds ``CSC``; a matric
  number carries ``0591``. That mapping is not a fact either context can derive from the
  other, and putting it anywhere else would spread it across the codebase.
* **Session to entry year.** That context knows a session id as an academic year; we need
  the four-digit year the session starts in.

Both are registered as plain data below, which is exactly the shape a composition root
or a test fixture can supply.
"""

from student_profile.domain.values import DepartmentCode, EntryYear
from student_profile.ports.department_code import DepartmentCodePort, MatricFormatInputs


class InMemoryDepartmentCodeAdapter(DepartmentCodePort):
    """Answers from a table registered up front, keyed by ``(program_id, session_id)``."""

    def __init__(self) -> None:
        self._placements: dict[tuple[str, str], MatricFormatInputs] = {}

    def register(
        self, program_id: str, session_id: str, department_code: str, entry_year: int
    ) -> None:
        """Record what Faculty & Department would answer for one program and session.

        Takes primitives rather than value objects so a caller does not have to import
        this context's domain to populate it, and so an invalid code registered by
        mistake fails here rather than at the moment a student is being created.
        """
        self._placements[(program_id, session_id)] = MatricFormatInputs(
            department_code=DepartmentCode(department_code),
            entry_year=EntryYear(entry_year),
        )

    async def format_inputs_for(
        self, program_id: str, session_id: str
    ) -> MatricFormatInputs | None:
        return self._placements.get((program_id, session_id))
