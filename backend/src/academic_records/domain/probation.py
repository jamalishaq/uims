"""Probation: the university's judgement on a cumulative grade point average.

Determined here and nowhere else. Enrollment carries a ``Standing`` of its own and keys
off it with nothing, deliberately — whether probation lowers the credit-load cap is an
open institutional fact (CLAUDE.md section 6) — and its adapter's docstring already says
that "Academic Records determines probation from CGPA against a threshold. Enrollment
receives the conclusion as an enum and never the number." This module is that threshold
and that conclusion.

**The threshold is an institutional fact**, confirmed rather than inferred: a CGPA below
1.50 puts a student on probation. It is a construction argument on
:class:`ProbationPolicy` for the same reason the grading scale is a value object — the
number belongs to the university, not to a comparison buried in a rule.

Two values on the enum and not three. There is no withdrawal state, because when a
student is withdrawn — one bad session, two consecutive, a floor below the probation
line — is a rule nobody has stated, and a `WITHDRAWN` value that nothing ever produced
would be worse than its absence. Enrollment's third value, ``UNKNOWN``, is not needed
here either: a record exists only once a grade has been submitted against it, so there is
no student in this context whose standing has never been assessed. Absence is expressed
by there being no record at all, which is what that port already returns ``None`` for.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from academic_records.domain.errors import InvalidProbationPolicyError

PROBATION_CGPA_THRESHOLD = Decimal("1.50")
"""The CGPA a student must reach to stay off probation.

A settled institutional fact (CLAUDE.md section 6), in the manner of the matric number
format and the 24-unit credit-load cap: confirmed with a human. It is a default here and a
construction argument on :class:`ProbationPolicy`, so a change is an argument at a call
site rather than an edit to a rule.
"""


class Standing(Enum):
    """How the university regards a student, on the strength of their CGPA."""

    GOOD_STANDING = "good standing"
    PROBATION = "probation"


@dataclass(frozen=True)
class ProbationPolicy:
    """The CGPA below which a student is on probation.

    The comparison is against the CGPA *as reported* — the two-decimal figure a transcript
    shows — and not against an unrounded ratio. A student shown 1.50 who was quietly on
    probation for being 1.4999 recurring is a support ticket nobody can answer, and the
    number the rule uses being the number the student sees is worth more than the third
    decimal place.
    """

    threshold: Decimal = PROBATION_CGPA_THRESHOLD

    def __post_init__(self) -> None:
        if not isinstance(self.threshold, Decimal):
            raise InvalidProbationPolicyError(
                "probation threshold must be a Decimal — binary floats do not compare "
                "predictably against a rounded CGPA"
            )
        if self.threshold <= 0:
            raise InvalidProbationPolicyError(
                f"probation threshold must be positive, got {self.threshold}; "
                "a threshold of zero would put nobody on probation, ever"
            )

    def standing_for(self, cgpa: Decimal) -> Standing:
        """Return the standing a student with this CGPA is in."""
        if not isinstance(cgpa, Decimal):
            raise InvalidProbationPolicyError(f"cgpa must be a Decimal, got {type(cgpa).__name__}")
        return Standing.PROBATION if cgpa < self.threshold else Standing.GOOD_STANDING

    def __str__(self) -> str:
        return f"probation below CGPA {self.threshold}"
