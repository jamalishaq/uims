"""Probation determination: a CGPA against a threshold.

**Confirmed with a human** (CLAUDE.md section 6): a CGPA below 1.50 puts a student on
probation. :data:`THRESHOLD_AS_CONFIRMED` is that fact written out here, checked against the
production constant, for the same reason the grading scale is — nobody should be able to
change what puts a real student on probation without this file failing.

The threshold is a boundary, so the tests are at it: 1.49, 1.50, 1.51. "Below" means
strictly below, and a student who reaches the line exactly is in good standing.
"""

from decimal import Decimal

import pytest

from academic_records.domain import (
    LASU_GRADING_SCALE,
    PROBATION_CGPA_THRESHOLD,
    AcademicRecord,
    CourseGrade,
    InvalidProbationPolicyError,
    ProbationPolicy,
    Standing,
    Transcript,
)

THRESHOLD_AS_CONFIRMED = Decimal("1.50")
"""A CGPA below this puts a student on probation. Confirmed with a human, not inferred."""


def test_the_threshold_is_the_confirmed_one() -> None:
    assert PROBATION_CGPA_THRESHOLD == THRESHOLD_AS_CONFIRMED
    assert ProbationPolicy().threshold == THRESHOLD_AS_CONFIRMED


@pytest.mark.parametrize(
    ("cgpa", "expected"),
    [
        (Decimal("0.00"), Standing.PROBATION),
        (Decimal("1.49"), Standing.PROBATION),
        (Decimal("1.50"), Standing.GOOD_STANDING),
        (Decimal("1.51"), Standing.GOOD_STANDING),
        (Decimal("5.00"), Standing.GOOD_STANDING),
    ],
)
def test_standing_turns_on_the_threshold(cgpa: Decimal, expected: Standing) -> None:
    """Strictly below. A student who reaches 1.50 exactly is in good standing."""
    assert ProbationPolicy().standing_for(cgpa) == expected


def test_there_are_exactly_two_standings() -> None:
    """No withdrawal state, and its absence is a decision.

    When a student is withdrawn — one bad session, two consecutive, some floor below the
    probation line — is a rule nobody has stated (CLAUDE.md section 6), and a value nothing
    ever produced would be worse than its absence.
    """
    assert set(Standing) == {Standing.GOOD_STANDING, Standing.PROBATION}


def test_the_threshold_is_a_construction_argument() -> None:
    """A policy change is an argument at a call site, not an edit to a rule."""
    stricter = ProbationPolicy(threshold=Decimal("2.00"))
    assert stricter.standing_for(Decimal("1.75")) == Standing.PROBATION
    assert ProbationPolicy().standing_for(Decimal("1.75")) == Standing.GOOD_STANDING


@pytest.mark.parametrize("threshold", [1.5, "1.50", None])
def test_a_threshold_that_is_not_a_decimal_is_refused(threshold: object) -> None:
    """Binary floats do not compare predictably against a rounded CGPA."""
    with pytest.raises(InvalidProbationPolicyError):
        ProbationPolicy(threshold=threshold)  # type: ignore[arg-type]


@pytest.mark.parametrize("threshold", [Decimal("0"), Decimal("-1.5")])
def test_a_threshold_of_zero_or_less_is_refused(threshold: Decimal) -> None:
    """It would put nobody on probation, ever, while looking as though it did something."""
    with pytest.raises(InvalidProbationPolicyError, match="positive"):
        ProbationPolicy(threshold=threshold)


def test_a_cgpa_that_is_not_a_decimal_is_refused() -> None:
    with pytest.raises(InvalidProbationPolicyError, match="Decimal"):
        ProbationPolicy().standing_for(1.75)  # type: ignore[arg-type]


# ---- against a real record, which is where it matters ----


def a_record(student_id: str, lines: list[tuple[str, int, int]]) -> AcademicRecord:
    """A record with the given ``(course_id, credit_units, score)`` lines in one semester."""
    record = AcademicRecord.open(student_id)
    for course_id, units, score in lines:
        record.record_grade(
            course_id=course_id, semester_id="sem-2026-1", score=score, credit_units=units
        )
    return record


def test_a_failing_student_is_put_on_probation() -> None:
    """3 units at 42 (D, 2.0) and 4 units at 30 (F, 0.0): 6.0 / 7 = 0.86."""
    record = a_record("stu-weak", [("CSC101", 3, 42), ("MTH101", 4, 30)])
    assert record.cgpa == Decimal("0.86")
    assert record.standing is Standing.PROBATION


def test_a_passing_student_stays_in_good_standing() -> None:
    """3 units at 75 (A, 5.0) and 4 units at 62 (B, 4.0): 31.0 / 7 = 4.43."""
    record = a_record("stu-strong", [("CSC101", 3, 75), ("MTH101", 4, 62)])
    assert record.cgpa == Decimal("4.43")
    assert record.standing is Standing.GOOD_STANDING


def test_a_records_policy_is_the_one_it_was_opened_with() -> None:
    """The same grades, two policies, two answers — decided by the record, not by a global."""
    lines = [("CSC101", 3, 45), ("MTH101", 3, 40)]  # D and D: 12.0 / 6 = 2.00
    lenient = a_record("stu-a", lines)
    strict = AcademicRecord.open("stu-b", probation=ProbationPolicy(threshold=Decimal("2.50")))
    for course_id, units, score in lines:
        strict.record_grade(
            course_id=course_id, semester_id="sem-2026-1", score=score, credit_units=units
        )

    assert lenient.cgpa == strict.cgpa == Decimal("2.00")
    assert lenient.standing is Standing.GOOD_STANDING
    assert strict.standing is Standing.PROBATION


def test_standing_is_judged_on_the_reported_cgpa_not_an_unrounded_ratio() -> None:
    """A student shown 1.50 is not quietly on probation for being 1.4999 recurring.

    9 units at 45 (D, 2.0) and 3 units at 39 (F, 0.0): 18.0 / 12 = 1.50 exactly, so this
    case does not depend on the rounding — but the raw ratio and the reported figure are the
    same object here by construction, which is the property being pinned.
    """
    record = a_record("stu-edge", [("CSC101", 9, 45), ("MTH101", 3, 39)])
    assert record.cgpa == Decimal("1.50")
    assert record.standing is Standing.GOOD_STANDING


def test_the_probation_rule_reads_the_cgpa_and_nothing_else() -> None:
    """Two records with the same CGPA reached differently get the same standing.

    Number of attempts, carry-overs, how bad the worst mark was: none of it enters. If any
    of those ever should, it is a conversation and a second field on the policy.
    """
    few = Transcript([_line("CSC101", 3, 42)])
    many = Transcript([_line(f"CRS{index}", 3, 42) for index in range(5)])
    policy = ProbationPolicy()
    assert few.cgpa == many.cgpa == Decimal("2.00")
    assert policy.standing_for(few.cgpa) == policy.standing_for(many.cgpa)


def _line(course_id: str, units: int, score: int) -> CourseGrade:
    return CourseGrade.award(
        course_id=course_id,
        semester_id="sem-2026-1",
        score=score,
        credit_units=units,
        scale=LASU_GRADING_SCALE,
    )
