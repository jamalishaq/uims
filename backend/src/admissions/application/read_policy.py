"""Reading back the three session-scoped policy objects a registrar wrote.

Each is a straight ``find`` returning ``None`` rather than raising, in the manner of
``ReadAccount.find`` and ``ReadAcademicRecord.find``: absence is a normal answer to a question
about identifiers a caller was handed by somebody else, and the routes above turn ``None``
into a 404 without having to catch anything.

That is deliberately *not* how the offer flow treats the same absences. There, a missing entry
requirement is an error and a missing alternative policy is a shrug — because those are
answers to "may this applicant be placed?", and a rule nobody wrote is different from a rule
that says no. Here the question is only "what is on file", and nothing is on file is a fact.
"""

from admissions.domain.admission_cycle import AdmissionCycle
from admissions.domain.alternative_program_policy import AlternativeProgramPolicy
from admissions.domain.entry_requirement import ProgramEntryRequirement
from admissions.ports.admission_cycle_repository import AdmissionCycleRepositoryPort
from admissions.ports.alternative_program_policy_repository import (
    AlternativeProgramPolicyRepositoryPort,
)
from admissions.ports.entry_requirement_repository import ProgramEntryRequirementRepositoryPort


class ReadAdmissionCycle:
    """What a program's intake looks like: quota, places claimed, places left."""

    def __init__(self, cycles: AdmissionCycleRepositoryPort) -> None:
        self._cycles = cycles

    async def find(self, program_id: str, session_id: str) -> AdmissionCycle | None:
        """The cycle, or ``None`` if none was opened for that program and session."""
        return await self._cycles.get(program_id, session_id)


class ReadEntryRequirement:
    """What a program demands of an applicant's subjects."""

    def __init__(self, requirements: ProgramEntryRequirementRepositoryPort) -> None:
        self._requirements = requirements

    async def find(self, program_id: str, session_id: str) -> ProgramEntryRequirement | None:
        """The requirement, or ``None`` if none was published."""
        return await self._requirements.get(program_id, session_id)


class ReadAlternativePolicy:
    """Where a program overflows to, in the order the offer flow will walk."""

    def __init__(self, policies: AlternativeProgramPolicyRepositoryPort) -> None:
        self._policies = policies

    async def find(self, program_id: str, session_id: str) -> AlternativeProgramPolicy | None:
        """The chain, or ``None`` if none was published.

        ``None`` and an empty chain mean the same thing to the offer flow — this program
        overflows nowhere — and are reported separately here anyway, because to a registrar
        "nobody wrote one" and "we wrote one that says nowhere" are different states of the
        work.
        """
        return await self._policies.get(program_id, session_id)
