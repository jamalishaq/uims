"""The real adapter behind ``DepartmentCodePort``: the two facts a matric number is built from.

Fed rather than reading Faculty & Department directly — rule (b), the
``BillingFinancialClearanceAdapter`` pattern. The composition root calls
``ReadProgramPlacement`` and hands back the two fields below.

Two translations live here, and CLAUDE.md section 3 puts both in exactly this file.

**Session to entry year.** That context knows a session as an academic year; a matric number
carries the four-digit year it starts in. That one is arithmetic-free and needs no policy.

**Alphabetic to numeric department code — and this one is not derivable.** Faculty & Department
holds ``CSC``; a matric number carries ``0591``. There is no rule connecting them: the numeric
codes are the university's own register, an institutional fact in CLAUDE.md section 6's sense,
and *nothing in this repository has ever stated one of them*. The in-memory adapter side-stepped
it by being handed numeric codes directly, which is fine for a fixture and is not an answer.

So the register is a **construction argument** — the arrangement ``ClearanceThresholds`` and
``GradingScale`` use — supplied by whoever composes the system from configuration, and changed
in one place. It is deliberately *not* defaulted: a default would be a guess at a real
university's numbering, baked into every student number ever issued and undiscoverable
afterwards, and CLAUDE.md section 6 is explicit that a wrong guess here becomes a load-bearing
assumption.

**An unregistered department reads as ``None``.** ``RegisterNewStudent`` turns that into
``ProgramPlacementUnknownError`` and refuses to create the student, which is the right failure:
issuing a matric number against a department code nobody confirmed would mint a permanent
identifier around a guess, and a matric number is not something a registrar can quietly take
back.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from student_profile.domain.values import DepartmentCode, EntryYear
from student_profile.ports.department_code import DepartmentCodePort, MatricFormatInputs


@dataclass(frozen=True)
class ProgramPlacement:
    """What Faculty & Department has to say about a program and a session, in primitives.

    ``department_code`` is that context's alphabetic code, untranslated. Translating it before
    it arrives would move the register out of this file, which is the one thing this file is for.
    """

    department_code: str
    session_start_year: int


class ProgramPlacementSource(Protocol):
    """Whatever can say which department is behind a program and when its session starts."""

    async def program_placement(self, program_id: str, session_id: str) -> ProgramPlacement | None:
        """The placement, or ``None`` if the program or the session is not known there."""
        ...


class FacultyDepartmentDepartmentCodeAdapter(DepartmentCodePort):
    """Reads Faculty & Department through a source, and answers in ``MatricFormatInputs``."""

    def __init__(self, source: ProgramPlacementSource, numeric_codes: Mapping[str, str]) -> None:
        """Hold the source and the university's register of numeric department codes.

        Args:
            source: whatever can answer where a program sits.
            numeric_codes: alphabetic code to the four digits a matric number carries, e.g.
                ``{"CSC": "0591"}``. Keys are matched case-insensitively, because Faculty &
                Department upper-cases its codes and a configuration file written by hand
                should not be able to fail on that.
        """
        self._source = source
        self._numeric_codes = {code.upper(): numeric for code, numeric in numeric_codes.items()}

    async def format_inputs_for(
        self, program_id: str, session_id: str
    ) -> MatricFormatInputs | None:
        """The inputs, or ``None`` if the program, the session or the code is not known."""
        placement = await self._source.program_placement(program_id, session_id)
        if placement is None:
            return None

        numeric = self._numeric_codes.get(placement.department_code.upper())
        if numeric is None:
            return None

        return MatricFormatInputs(
            department_code=DepartmentCode(numeric),
            entry_year=EntryYear(placement.session_start_year),
        )
