"""Query port into Faculty & Department, for the two facts an application is checked against.

Before an application is stored, two things have to be true of the program named on it:
that it exists, and that it is admitting for the session applied for (CLAUDE.md
section 3). Neither is Admissions' to know — programs belong to Faculty & Department —
and both are pulled synchronously because they are needed to make a decision *now*. This
is a query, not an event: waiting for a reply is exactly the smell test CLAUDE.md
section 3 gives for choosing a port over an event.

The return type is ours. :class:`ProgramInfo` is expressed in Admissions' own language and
no Faculty & Department type appears anywhere in this file; the translation happens in the
adapter, which is the whole point of an anti-corruption layer. That matters more here than
it looks: over there a program is an aggregate with a department, a name and a code, and
none of that is any of this context's business. Two fields are.

Keyed by ``(program_id, session_id)``, like every other thing Admissions asks about a
program. Faculty & Department holds ``is_admitting`` as a flag on the program itself with
no session dimension; reconciling that with a question asked per session is the adapter's
work, and if admissions windows ever become genuinely per-session over there, this port
does not change.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ProgramInfo:
    """What Faculty & Department has to confirm before an application may be stored."""

    program_id: str
    is_admitting: bool


class ProgramInfoPort(ABC):
    """Reads whether a program exists and is admitting for a session."""

    @abstractmethod
    def program_for(self, program_id: str, session_id: str) -> ProgramInfo | None:
        """Return what is known about the program, or ``None`` if it is not known there.

        ``None`` is an answer, not a failure: asking about a program that does not exist
        is a question with a correct negative reply. It is also a different answer from a
        program that exists and is closed — one is an id nobody recognises, the other is a
        real program not taking applicants — and the application layer makes something of
        the difference.
        """
