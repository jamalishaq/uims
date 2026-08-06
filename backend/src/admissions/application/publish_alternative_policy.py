"""Publish where a program overflows to when it fills up, in preference order.

The chain ``MakeOfferToApplicant`` walks. Order is the whole content of it: first qualifying
program with a place left takes the applicant, so re-ordering the list changes who ends up
where.

**Owned by a faculty officer, not a department registrar** (CLAUDE.md section 6), and this is
the one policy object of the three where that differs. A chain names *other departments'*
programs and spends *their* quota — Computer Science overflowing into Mathematics consumes
places the Mathematics registrar set — so it cannot be one department's to write unilaterally.
Agreed at faculty level, where every department it affects is in the room.

**That ownership is not enforced here yet.** There is no authentication, so nothing checks who
is calling; and checking that every program named sits in the writer's faculty is a
cross-context read Admissions cannot make today (`ProgramInfo` carries no faculty). Both
arrive with identity. What this file can do is refuse to be the place the decision is
forgotten, which is why it is written down here.
"""

from dataclasses import dataclass

from admissions.domain.alternative_program_policy import AlternativeProgramPolicy
from admissions.ports.alternative_program_policy_repository import (
    AlternativeProgramPolicyRepositoryPort,
)


@dataclass(frozen=True)
class PublishAlternativePolicyCommand:
    """A program's fallback chain, best first.

    An empty chain is legal and means the program has nowhere to overflow to: an applicant it
    cannot seat is told no offer is available. Some programs genuinely have no fallback, and
    demanding a token alternative would be inventing policy.
    """

    program_id: str
    session_id: str
    alternatives: tuple[str, ...] = ()


class PublishAlternativePolicy:
    """Write down a program's fallback chain for a session."""

    def __init__(self, policies: AlternativeProgramPolicyRepositoryPort) -> None:
        self._policies = policies

    async def execute(self, command: PublishAlternativePolicyCommand) -> AlternativeProgramPolicy:
        """Build the policy, letting the domain judge it, and store it.

        Returns:
            AlternativeProgramPolicy: the published chain, in the order given.

        Raises:
            DuplicateAggregateError: a policy is already published for that program and
                session. Not an overwrite, for ``PublishEntryRequirement``'s reason: a cohort
                part-way through placement must not be routed by two different chains.
            SelfReferentialAlternativeError: the chain lists the program it is the fallback
                for. The cycle it would retry is the one already found full.
            DuplicateAlternativeError: the chain names a program more than once, which is
                never a longer chain — "first qualifying cycle with room" makes the second
                occurrence unreachable.
            MissingIdentifierError: an identifier is blank.
        """
        policy = AlternativeProgramPolicy.for_program(
            command.program_id,
            command.session_id,
            alternatives=command.alternatives,
        )
        await self._policies.add(policy)
        return policy
