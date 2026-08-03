"""The LASU grading scale, checked against the table as it was given to us.

**This module is the source of truth.** The build playbook's Phase 4.2 asks for the scale to
be written into the test and then confirmed with a human before merging, per CLAUDE.md
section 6's escalation path — a grading scale is an institutional fact, and a wrong guess
becomes a load-bearing assumption baked into every transcript the system will ever produce.

:data:`LASU_SCALE_AS_CONFIRMED` below is that table, typed out independently of the
production constant it is checked against. The two agreeing is the whole point: if somebody
edits ``LASU_GRADING_SCALE`` without a conversation, this file fails and says so.

**Confirmed:** five bands, not six. There is no E — D spans the whole of 40-49 — and the
pass mark is 40.
"""

from decimal import Decimal

import pytest

from academic_records.domain import (
    LASU_GRADING_SCALE,
    GradeBand,
    GradingScale,
    InvalidGradingScaleError,
    InvalidScoreError,
)

LASU_SCALE_AS_CONFIRMED = [
    # (min_score, max_score, letter, grade_point)
    (70, 100, "A", "5.0"),
    (60, 69, "B", "4.0"),
    (50, 59, "C", "3.0"),
    (40, 49, "D", "2.0"),
    (0, 39, "F", "0.0"),
]
"""Lagos State University's five-point scale, as confirmed with a human."""

PASS_MARK = 40


def test_scale_has_exactly_the_confirmed_bands() -> None:
    """The production constant is the confirmed table, band for band, in the same order."""
    assert [
        (band.min_score, band.max_score, band.letter, str(band.grade_point))
        for band in LASU_GRADING_SCALE.bands
    ] == LASU_SCALE_AS_CONFIRMED


@pytest.mark.parametrize(("low", "high", "letter", "grade_point"), LASU_SCALE_AS_CONFIRMED)
def test_every_score_in_a_band_gets_that_bands_grade(
    low: int, high: int, letter: str, grade_point: str
) -> None:
    """Both ends of every band inclusive, plus a point inside it."""
    for score in (low, (low + high) // 2, high):
        awarded = LASU_GRADING_SCALE.grade_for(score)
        assert (awarded.letter, awarded.grade_point) == (letter, Decimal(grade_point)), score


@pytest.mark.parametrize(
    ("score", "letter"),
    [(39, "F"), (40, "D"), (49, "D"), (50, "C"), (59, "C"), (60, "B"), (69, "B"), (70, "A")],
)
def test_band_boundaries_fall_on_the_confirmed_side(score: int, letter: str) -> None:
    """The seams, one mark either side. Where an off-by-one would live and never be noticed."""
    assert LASU_GRADING_SCALE.grade_for(score).letter == letter


@pytest.mark.parametrize("score", [PASS_MARK, 55, 70, 100])
def test_a_mark_at_or_above_the_pass_mark_is_a_pass(score: int) -> None:
    assert LASU_GRADING_SCALE.grade_for(score).is_pass


@pytest.mark.parametrize("score", [0, 20, PASS_MARK - 1])
def test_a_mark_below_the_pass_mark_is_a_fail_worth_nothing(score: int) -> None:
    awarded = LASU_GRADING_SCALE.grade_for(score)
    assert not awarded.is_pass
    assert awarded.grade_point == Decimal("0.0")


def test_pass_mark_is_derived_from_the_bands_rather_than_configured() -> None:
    """A pass is a band worth something. The two cannot be set to disagree."""
    assert LASU_GRADING_SCALE.pass_mark == PASS_MARK


@pytest.mark.parametrize("score", [-1, 101, 1000])
def test_a_score_outside_the_examinable_range_is_refused(score: int) -> None:
    with pytest.raises(InvalidScoreError):
        LASU_GRADING_SCALE.grade_for(score)


@pytest.mark.parametrize("score", [70.0, "70", True, None])
def test_a_score_that_is_not_a_whole_number_is_refused(score: object) -> None:
    """``True`` is an ``int`` to Python and a data-entry accident to a registry."""
    with pytest.raises(InvalidScoreError):
        LASU_GRADING_SCALE.grade_for(score)  # type: ignore[arg-type]


# ---- the class itself, which is what makes a *different* scale safe to build ----


def test_a_scale_with_a_gap_is_refused() -> None:
    """A mark that maps to nothing is a transcript line that cannot be produced."""
    with pytest.raises(InvalidGradingScaleError, match="fall between bands"):
        GradingScale(
            [
                GradeBand(50, 100, "A", Decimal("5.0")),
                GradeBand(0, 44, "F", Decimal("0.0")),
            ]
        )


def test_a_scale_with_overlapping_bands_is_refused() -> None:
    """A mark that maps to two letters would be decided by the order they were written in."""
    with pytest.raises(InvalidGradingScaleError, match="overlap"):
        GradingScale(
            [
                GradeBand(40, 100, "A", Decimal("5.0")),
                GradeBand(0, 45, "F", Decimal("0.0")),
            ]
        )


@pytest.mark.parametrize(
    ("bands", "match"),
    [
        ([GradeBand(10, 100, "A", Decimal("5.0"))], "would map to nothing"),
        ([GradeBand(0, 90, "A", Decimal("5.0"))], "would map to nothing"),
        ([], "at least one band"),
    ],
)
def test_a_scale_that_does_not_cover_every_score_is_refused(
    bands: list[GradeBand], match: str
) -> None:
    with pytest.raises(InvalidGradingScaleError, match=match):
        GradingScale(bands)


def test_a_scale_on_which_nothing_passes_is_refused() -> None:
    with pytest.raises(InvalidGradingScaleError, match="nothing is a pass"):
        GradingScale([GradeBand(0, 100, "F", Decimal("0.0"))])


def test_a_scale_with_repeated_letters_is_refused() -> None:
    with pytest.raises(InvalidGradingScaleError, match="distinct"):
        GradingScale(
            [
                GradeBand(50, 100, "A", Decimal("5.0")),
                GradeBand(0, 49, "A", Decimal("0.0")),
            ]
        )


def test_a_band_must_carry_a_decimal_grade_point() -> None:
    """Binary floats do not add up predictably, and a CGPA is checked by hand."""
    with pytest.raises(InvalidGradingScaleError, match="Decimal"):
        GradeBand(70, 100, "A", 5.0)  # type: ignore[arg-type]


def test_a_band_may_not_run_backwards() -> None:
    with pytest.raises(InvalidGradingScaleError, match="backwards"):
        GradeBand(100, 70, "A", Decimal("5.0"))


def test_the_scale_is_a_construction_argument_so_a_faculty_may_have_its_own() -> None:
    """features.md section 7 asks for a scale configurable per faculty.

    Under this design that is a second constant built from the same class, not a second
    code path — nothing downstream of ``grade_for`` learns that more than one exists.
    """
    four_point = GradingScale(
        [
            GradeBand(70, 100, "A", Decimal("4.0")),
            GradeBand(60, 69, "B", Decimal("3.0")),
            GradeBand(50, 59, "C", Decimal("2.0")),
            GradeBand(45, 49, "D", Decimal("1.0")),
            GradeBand(0, 44, "F", Decimal("0.0")),
        ]
    )
    assert four_point.grade_for(75).grade_point == Decimal("4.0")
    assert four_point.pass_mark == 45
    assert LASU_GRADING_SCALE.grade_for(75).grade_point == Decimal("5.0")


def test_the_bands_cannot_be_edited_through_the_property() -> None:
    assert isinstance(LASU_GRADING_SCALE.bands, tuple)
