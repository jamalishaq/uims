"""The grading scale: what a raw score is worth.

This context owns the mapping from a mark to a letter and a grade point, and it is the
only context that has an opinion about it. Faculty & Department validates a score's range
and publishes it untranslated; Enrollment deliberately never sees a grade at all, because
"has this student passed the prerequisite?" is a scale question and answering it there
would be that context quietly acquiring an opinion about what a pass is. Both of those
files say so in their own words. This module is the other end of both statements.

**The scale is an institutional fact** (CLAUDE.md section 6), in the manner of the matric
number format and the 24-unit credit-load cap: confirmed with a human rather than
inferred. :data:`LASU_GRADING_SCALE` is that confirmation, and
``tests/academic_records/domain/test_grading_scale.py`` holds the same table written out
independently as the source of truth it is checked against.

It is a value object and not an ``if/elif`` ladder for the reason ``CreditLoadPolicy`` and
``MatricNumberFormat`` are: a change to the scale should be a construction argument. That
matters more here than in either of those, because features.md section 7 asks for the
scale to be *configurable per faculty* — which under this design is a second constant
built from the same class, not a second code path, and nothing downstream of
``grade_for`` needs to know that more than one exists.

What a pass is, is not a separate number. A band's grade point is zero exactly when the
band is a fail, so :attr:`AwardedGrade.is_pass` is derived rather than configured — a
scale carrying both a pass mark and a set of grade points could be built with the two
disagreeing, and then "passed" and "counted towards the CGPA" would mean different things
for the same course.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

from academic_records.domain.errors import InvalidGradingScaleError
from academic_records.domain.values import MAX_SCORE, MIN_SCORE, require_score, require_text


@dataclass(frozen=True)
class AwardedGrade:
    """What a score came out as: a letter, a grade point, and whether it is a pass.

    Frozen, and produced only by :meth:`GradingScale.grade_for`. There is no constructor
    path that lets a caller pair a letter with a grade point of their own choosing.
    """

    letter: str
    grade_point: Decimal

    @property
    def is_pass(self) -> bool:
        """Whether the course was passed. A fail is worth nothing, and that is the same fact."""
        return self.grade_point > 0

    def __str__(self) -> str:
        return f"{self.letter} ({self.grade_point})"


@dataclass(frozen=True, order=True)
class GradeBand:
    """One row of a grading scale: a closed score range, its letter and its grade point.

    Both ends are inclusive. ``GradeBand(70, 100, "A", Decimal("5.0"))`` is the whole of
    the A range and not "70 up to but excluding 100" — the boundary that trips people up
    is stated once here rather than at every comparison.
    """

    min_score: int
    max_score: int
    letter: str
    grade_point: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "min_score", require_score(self.min_score, "band lower bound"))
        object.__setattr__(self, "max_score", require_score(self.max_score, "band upper bound"))
        object.__setattr__(self, "letter", require_text(self.letter, "grade letter").upper())
        if self.min_score > self.max_score:
            raise InvalidGradingScaleError(
                f"band {self.letter} runs from {self.min_score} to {self.max_score}, "
                "which is backwards"
            )
        if not isinstance(self.grade_point, Decimal):
            raise InvalidGradingScaleError(
                f"band {self.letter} must carry a Decimal grade point, "
                f"got {type(self.grade_point).__name__} — binary floats do not add up "
                "predictably and a CGPA is arithmetic somebody checks by hand"
            )
        if self.grade_point < 0:
            raise InvalidGradingScaleError(
                f"band {self.letter} has a negative grade point {self.grade_point}"
            )

    def contains(self, score: int) -> bool:
        return self.min_score <= score <= self.max_score


class GradingScale:
    """An ordered set of bands covering every possible score exactly once.

    The two validations are the whole of the class's reason to exist. A gap means some
    real mark maps to nothing and a student's transcript line cannot be produced; an
    overlap means a mark maps to two letters and which one wins depends on the order the
    bands happened to be written in. Both are the sort of thing that is discovered years
    later on one student's record, so they are rejected at construction.
    """

    def __init__(self, bands: Iterable[GradeBand]) -> None:
        self._bands = _validated_bands(bands)

    @property
    def bands(self) -> tuple[GradeBand, ...]:
        """The bands, highest-scoring first. A tuple: a caller cannot rewrite the scale."""
        return self._bands

    @property
    def pass_mark(self) -> int:
        """The lowest score that is worth anything — derived from the bands, not configured.

        The bottom of the lowest band whose grade point is above zero.
        """
        return min(band.min_score for band in self._bands if band.grade_point > 0)

    def grade_for(self, score: int) -> AwardedGrade:
        """Return what ``score`` is worth on this scale.

        Raises:
            InvalidScoreError: the score is not a whole mark out of 100.
        """
        score = require_score(score)
        for band in self._bands:
            if band.contains(score):
                return AwardedGrade(letter=band.letter, grade_point=band.grade_point)
        raise InvalidGradingScaleError(  # pragma: no cover - construction guarantees coverage
            f"no band covers score {score}, which a validated scale cannot allow"
        )

    def __repr__(self) -> str:
        return f"GradingScale({[band.letter for band in self._bands]})"


def _validated_bands(bands: Iterable[GradeBand]) -> tuple[GradeBand, ...]:
    """Every band a ``GradeBand``, together covering ``MIN_SCORE``-``MAX_SCORE`` with no seam."""
    ordered = tuple(bands)
    if not ordered:
        raise InvalidGradingScaleError("a grading scale needs at least one band")
    if any(not isinstance(band, GradeBand) for band in ordered):
        raise InvalidGradingScaleError("every band must be a GradeBand")

    ascending = tuple(sorted(ordered, key=lambda band: band.min_score))

    if ascending[0].min_score != MIN_SCORE:
        raise InvalidGradingScaleError(
            f"the lowest band starts at {ascending[0].min_score}; "
            f"scores from {MIN_SCORE} would map to nothing"
        )
    if ascending[-1].max_score != MAX_SCORE:
        raise InvalidGradingScaleError(
            f"the highest band ends at {ascending[-1].max_score}; "
            f"scores up to {MAX_SCORE} would map to nothing"
        )

    for lower, upper in pairwise(ascending):
        if upper.min_score <= lower.max_score:
            raise InvalidGradingScaleError(
                f"bands {lower.letter} ({lower.min_score}-{lower.max_score}) and "
                f"{upper.letter} ({upper.min_score}-{upper.max_score}) overlap"
            )
        if upper.min_score != lower.max_score + 1:
            raise InvalidGradingScaleError(
                f"scores {lower.max_score + 1}-{upper.min_score - 1} fall between bands "
                f"{lower.letter} and {upper.letter} and map to nothing"
            )

    if not any(band.grade_point > 0 for band in ascending):
        raise InvalidGradingScaleError("a scale on which nothing is a pass cannot grade anybody")

    letters = [band.letter for band in ascending]
    if len(set(letters)) != len(letters):
        raise InvalidGradingScaleError(f"band letters must be distinct, got {letters}")

    return tuple(reversed(ascending))


LASU_GRADING_SCALE = GradingScale(
    [
        GradeBand(70, 100, "A", Decimal("5.0")),
        GradeBand(60, 69, "B", Decimal("4.0")),
        GradeBand(50, 59, "C", Decimal("3.0")),
        GradeBand(40, 49, "D", Decimal("2.0")),
        GradeBand(0, 39, "F", Decimal("0.0")),
    ]
)
"""Lagos State University's five-point scale, with 40 as the pass mark.

**Confirmed with a human, not inferred** (CLAUDE.md section 6). Five bands and not six:
there is no E, and D spans the whole of 40-49. The build playbook's Phase 4.2 asks for
exactly this confirmation before the phase is merged.
"""
