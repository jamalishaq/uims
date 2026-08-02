"""The anti-corruption adapter behind ``ProgramInfoPort``.

This is where Faculty & Department's model would be translated into ours — and the reason
it is *fed* data rather than reading that context directly is the dependency rule itself:
no module may import another context at any layer, adapters included (CLAUDE.md section 4,
and the architecture fitness test enforces it). Whatever sits on the other side of this
port is reached over a boundary that is not a Python import: in Phase 6 that is Faculty &
Department's read-model or API, and this class is replaced by one that speaks to it.

One translation lives here, and only here: **a session-less flag answering a per-session
question.** Over there, ``Program.is_admitting`` is a property of the program, opened and
closed by a deliberate act. Admissions asks per session, because every other thing it holds
about a program — the entry requirement, the cycle, the fallback chain — is per session,
and a question that dropped the session would be the one lookup in this context that could
answer for the wrong year. Registering the pair is what reconciles the two, and it is the
one place the reconciliation changes.
"""

from admissions.ports.program_info import ProgramInfo, ProgramInfoPort


class InMemoryProgramInfoAdapter(ProgramInfoPort):
    """Answers from a table registered up front, keyed by ``(program_id, session_id)``."""

    def __init__(self) -> None:
        self._programs: dict[tuple[str, str], ProgramInfo] = {}

    def register(self, program_id: str, session_id: str, *, admitting: bool) -> None:
        """Record what Faculty & Department would answer for one program and session.

        Takes primitives rather than a domain type so a caller does not have to import
        anything to populate it, and ``admitting`` is keyword-only because a bare boolean
        at a call site says nothing about which way round it goes.
        """
        self._programs[(program_id, session_id)] = ProgramInfo(
            program_id=program_id,
            is_admitting=admitting,
        )

    def program_for(self, program_id: str, session_id: str) -> ProgramInfo | None:
        return self._programs.get((program_id, session_id))
