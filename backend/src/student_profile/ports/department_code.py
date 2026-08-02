"""Query port into Faculty & Department, for the facts a matric number is built from.

A matric number needs two things this context does not own: the numeric code of the
department a program belongs to, and the year the entry session starts in. Both are
Faculty & Department's to know (CLAUDE.md section 3), and both are pulled synchronously
because they are needed to make a decision *now* — this is a query, not an event.

The return type is ours. :class:`MatricFormatInputs` is expressed in Student Profile's
own language, and no Faculty & Department type appears anywhere in this file: the
translation from whatever that context publishes into these two values happens in the
adapter, which is the whole point of an anti-corruption layer. Notably, Faculty &
Department's ``Department.code`` is alphabetic (``CSC``); the four numeric digits a
matric number carries are produced by the adapter, and if that mapping ever changes it
changes in one file.

Keyed by ``(program_id, session_id)`` rather than by a department id because that is
what both creation paths actually hold: ``StudentMatriculated`` carries the offered
program and the session, and neither of them tells this context which department is
behind the program.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from student_profile.domain.values import DepartmentCode, EntryYear


@dataclass(frozen=True)
class MatricFormatInputs:
    """Everything Faculty & Department has to supply before a matric number can exist."""

    department_code: DepartmentCode
    entry_year: EntryYear


class DepartmentCodePort(ABC):
    """Reads the department code and entry year behind a program and a session."""

    @abstractmethod
    def format_inputs_for(self, program_id: str, session_id: str) -> MatricFormatInputs | None:
        """Return the inputs, or ``None`` if the program or session is not known there.

        ``None`` is an answer, not a failure: asking about a program that does not exist
        is a question with a correct negative reply. Whether that should stop a student
        being registered is the caller's judgment, and the application layer makes it.
        """
