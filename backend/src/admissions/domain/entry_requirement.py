"""What a program demands of an applicant's UTME subjects.

Admissions-owned policy data, scoped to a session (CLAUDE.md section 3). Entry
requirements are set by the university and change between sessions; holding them here,
keyed by ``(program_id, session_id)``, is what lets last year's requirement stay readable
after this year's is published — an applicant screened in 2026 was screened against the
2026 rule, and a record that could not say so would be unable to answer a complaint.

A Nigerian entry requirement is two kinds of demand at once. Some subjects are simply
required: Computer Science wants Use of English, Mathematics and Physics from everybody.
The remaining slot is a choice — one of Chemistry, Biology, Geography, Economics or
Agricultural Science — and the applicant picks. Both are modelled, because collapsing the
choice into "required" would reject qualified applicants and dropping it would admit
unqualified ones.

Two construction guards are worth their weight, and both come from the same place: a UTME
result is exactly four distinct subjects.

* A requirement demanding more than four things could not be met by anyone. That is a
  policy typo, not a strict programme, and catching it when the requirement is written
  beats discovering it when a whole cohort is turned away.
* Demands must not overlap. If Chemistry could satisfy both a one-of group and a required
  subject, one subject on one result would be counted twice — the same double-counting
  ``UtmeResult`` refuses when it insists its four subjects are distinct. Forbidding the
  overlap at construction is also what keeps the check in ``SubjectCombinationRule`` a
  straight read rather than a matching problem.

What is *not* here is a cut-off mark. Whether a program has a minimum aggregate, and what
it is, is an institutional fact (CLAUDE.md section 6) — this requirement judges subject
combinations, and adding a score threshold later is a decision somebody makes rather than
an assumption already baked in.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from admissions.domain.errors import (
    InvalidSubjectGroupError,
    OverlappingRequirementError,
    UnsatisfiableRequirementError,
)
from admissions.domain.values import UTME_SUBJECT_COUNT, require_identifier, require_text


def _normalise_subject(subject: str) -> str:
    """Upper-case and strip, exactly as ``UtmeSubjectScore`` does to a sat subject.

    The two normalisations have to agree, or a requirement written ``"Chemistry"`` would
    fail to match a result carrying ``"CHEMISTRY"`` and nobody would ever qualify.
    """
    return require_text(subject, "subject").upper()


@dataclass(frozen=True)
class SubjectGroup:
    """A choice of subjects, any one of which satisfies the demand.

    Written ``one of {CHEMISTRY, BIOLOGY, GEOGRAPHY}``: the applicant needs one, and
    holding two is no better than holding one — the extra sits in a slot the program had
    no opinion about.
    """

    options: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "options", frozenset(_normalise_subject(option) for option in self.options)
        )
        if not self.options:
            raise InvalidSubjectGroupError("a one-of group must offer at least one subject")

    def satisfied_by(self, subjects: frozenset[str]) -> bool:
        """Whether any option appears among the subjects sat."""
        return bool(self.options & subjects)

    def __str__(self) -> str:
        return f"one of {{{', '.join(sorted(self.options))}}}"


class ProgramEntryRequirement:
    """The UTME subject combination one program demands for one session."""

    def __init__(
        self,
        program_id: str,
        session_id: str,
        *,
        required_subjects: Iterable[str] = (),
        one_of_groups: Iterable[SubjectGroup] = (),
    ) -> None:
        self._program_id = require_identifier(program_id, "program_id")
        self._session_id = require_identifier(session_id, "session_id")
        self._required_subjects = frozenset(
            _normalise_subject(subject) for subject in required_subjects
        )
        groups = tuple(one_of_groups)
        if any(not isinstance(group, SubjectGroup) for group in groups):
            raise InvalidSubjectGroupError("one_of_groups must be SubjectGroup values")
        self._one_of_groups = groups
        self._reject_unsatisfiable_demand()
        self._reject_overlapping_demands()

    @classmethod
    def for_program(
        cls,
        program_id: str,
        session_id: str,
        *,
        required_subjects: Iterable[str] = (),
        one_of_groups: Iterable[SubjectGroup] = (),
    ) -> "ProgramEntryRequirement":
        """Publish a program's requirement for a session.

        A requirement demanding nothing at all is legal and qualifies everybody: a program
        that admits on aggregate alone is a real thing, and forcing a token subject on it
        would be inventing policy.
        """
        return cls(
            program_id,
            session_id,
            required_subjects=required_subjects,
            one_of_groups=one_of_groups,
        )

    @property
    def program_id(self) -> str:
        return self._program_id

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def required_subjects(self) -> frozenset[str]:
        """Subjects every applicant must have sat. A frozenset: callers cannot add to it."""
        return self._required_subjects

    @property
    def one_of_groups(self) -> tuple[SubjectGroup, ...]:
        """The choices, in the order the requirement was written."""
        return self._one_of_groups

    @property
    def demand_count(self) -> int:
        """How many of an applicant's four subjects this requirement speaks for."""
        return len(self._required_subjects) + len(self._one_of_groups)

    def _reject_unsatisfiable_demand(self) -> None:
        if self.demand_count > UTME_SUBJECT_COUNT:
            raise UnsatisfiableRequirementError(
                f"requirement for program {self._program_id} demands {self.demand_count} "
                f"subjects, more than the {UTME_SUBJECT_COUNT} a UTME result carries"
            )

    def _reject_overlapping_demands(self) -> None:
        """One subject may answer one demand. Nothing counts twice."""
        seen = set(self._required_subjects)
        for group in self._one_of_groups:
            clash = group.options & seen
            if clash:
                raise OverlappingRequirementError(
                    f"requirement for program {self._program_id} lists "
                    f"{', '.join(sorted(clash))} in more than one demand"
                )
            seen |= group.options

    def __repr__(self) -> str:
        return (
            f"ProgramEntryRequirement(program_id={self._program_id!r}, "
            f"session_id={self._session_id!r}, "
            f"required_subjects={sorted(self._required_subjects)}, "
            f"one_of_groups={[str(group) for group in self._one_of_groups]})"
        )
