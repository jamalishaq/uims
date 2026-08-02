"""The one judgement of whether a UTME combination qualifies an applicant for a program.

A domain service rather than a method, because CLAUDE.md section 3 says it has two call
sites: screening an applicant against the program they applied for, and filtering the
alternative programs they might be offered instead. One implementation, two call sites.
Two copies of this loop would drift, and the drift would show up as an applicant screened
out of Computer Science being offered Computer Science as somebody else's alternative.

Nothing here assumes it is screening. It is handed a requirement and a result and answers
about those two, which is what lets the alternative-offer flow call it in a loop over
programs the applicant never applied for.

Stateless, like ``MatricNumberIssuer``: the state it reasons about — the requirement, the
result — is passed in, so one instance can be shared and none can go stale.

The judgement itself lives here rather than on either object because it belongs to
neither. A ``UtmeResult`` that knew about programs would have to be rebuilt whenever a
requirement changed (``values.py`` says as much), and a requirement that knew how to read
a result would be the only reason it needed to know a result exists.
"""

from admissions.domain.entry_requirement import ProgramEntryRequirement
from admissions.domain.values import UtmeResult


class SubjectCombinationRule:
    """Judges a ``UtmeResult`` against a ``ProgramEntryRequirement``."""

    def qualifies(self, requirement: ProgramEntryRequirement, result: UtmeResult) -> bool:
        """Whether these subjects satisfy every demand the program makes."""
        return not self.unmet(requirement, result)

    def unmet(self, requirement: ProgramEntryRequirement, result: UtmeResult) -> tuple[str, ...]:
        """The demands these subjects do *not* satisfy, described for a human to read.

        Required subjects are named; a choice the applicant met none of is rendered whole,
        as ``one of {BIOLOGY, GEOGRAPHY}``, because naming a single option would read as
        advice the program never gave.

        This is what lets ``ScreenApplicant`` tell an applicant why the answer was no
        without working it out a second time, and it is why :meth:`qualifies` is defined
        in terms of it — a rule that decided in one place and explained in another could
        eventually decide one thing and explain the other.

        Subjects sat that the requirement has no opinion about are ignored: a fourth
        subject the program never asked for disqualifies nobody.
        """
        subjects = result.subjects
        missing = [
            subject for subject in sorted(requirement.required_subjects) if subject not in subjects
        ]
        unsatisfied = [
            str(group) for group in requirement.one_of_groups if not group.satisfied_by(subjects)
        ]
        return (*missing, *unsatisfied)
