"""Publish what a program demands of an applicant's UTME subjects, for one session.

The rule screening is performed against. Its absence is an *error* rather than a screening
outcome (``EntryRequirementNotFoundError``): an unqualified applicant means the university
looked at a rule and said no, a missing rule means nobody wrote one down, and screening
against nothing would quietly turn away everyone who applied to that program.

**Owned by the department registrar** (CLAUDE.md section 6). A department knows what subjects
its own program needs, and this is where it says so.

Session-scoped, so publishing the 2027 requirement leaves the 2026 one readable — an applicant
screened in 2026 was screened against the 2026 rule, and a record that could not say so would
be unable to answer a complaint.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from admissions.domain.entry_requirement import ProgramEntryRequirement, SubjectGroup
from admissions.ports.entry_requirement_repository import ProgramEntryRequirementRepositoryPort


@dataclass(frozen=True)
class PublishEntryRequirementCommand:
    """A program's demands, in primitives.

    ``one_of_groups`` arrives as a sequence of sequences rather than as ``SubjectGroup``
    values, because a command is what crosses from a transport and a transport does not hold
    this context's value objects. Building them is this use case's job, and their construction
    guards — a group must offer at least one subject — run there.

    Both default to empty. A requirement demanding nothing is legal and means the program
    takes any four subjects, which is a real policy some programs have.
    """

    program_id: str
    session_id: str
    required_subjects: tuple[str, ...] = ()
    one_of_groups: tuple[tuple[str, ...], ...] = field(default_factory=tuple)


class PublishEntryRequirement:
    """Write down what a program asks for."""

    def __init__(self, requirements: ProgramEntryRequirementRepositoryPort) -> None:
        self._requirements = requirements

    async def execute(self, command: PublishEntryRequirementCommand) -> ProgramEntryRequirement:
        """Build the requirement, letting the domain judge it, and store it.

        Returns:
            ProgramEntryRequirement: the published requirement.

        Raises:
            DuplicateAggregateError: a requirement is already published for that program and
                session. Republishing is not an overwrite: a cohort part-way through
                screening must not be judged against two different rules.
            UnsatisfiableRequirementError: more demands than a UTME result carries four of.
            OverlappingRequirementError: one subject named in more than one demand.
            InvalidSubjectGroupError: a one-of group offering no subjects.
            MissingIdentifierError: an identifier or subject name is blank.
        """
        requirement = ProgramEntryRequirement.for_program(
            command.program_id,
            command.session_id,
            required_subjects=command.required_subjects,
            one_of_groups=_groups(command.one_of_groups),
        )
        await self._requirements.add(requirement)
        return requirement


def _groups(raw: Iterable[Iterable[str]]) -> tuple[SubjectGroup, ...]:
    """Turn sequences of subject names into the domain's one-of groups."""
    return tuple(SubjectGroup(frozenset(options)) for options in raw)
