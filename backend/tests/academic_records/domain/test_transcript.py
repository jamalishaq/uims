"""GPA and CGPA over multiple semesters, against a fixture computed by hand.

The build playbook's Phase 4.2 verification: "CGPA over multiple semesters matches
hand-computed fixture". :data:`FIXTURE` below is that computation, written out with every
intermediate value — the letter, the grade point and the weighted contribution of each line
— so the assertion is against arithmetic a person did rather than against whatever the code
happens to produce.

The formula is features.md section 8's: **GPA = Σ(grade point x credit units) / Σ(credit
units)**, reported to two decimal places, rounded half up.

The fixture is built to exercise the two rules that were confirmed with a human rather than
inferred:

* ``MTH102`` is **failed in one semester and passed in a later one**, and both attempts
  count towards the CGPA. That is the confirmed carry-over rule (CLAUDE.md section 6):
  there is no replacement, no best-attempt, no supersession.
* ``GNS101`` scores 45 and ``CSC201`` scores 49 — both inside the confirmed D band, which
  under the six-band scale this university does *not* use would have been an E worth half
  as much.
"""

from decimal import Decimal

import pytest

from academic_records.domain import (
    LASU_GRADING_SCALE,
    CourseGrade,
    GradeNotRecordedError,
    MissingIdentifierError,
    Transcript,
)

FIRST = "sem-2026-1"
SECOND = "sem-2026-2"
THIRD = "sem-2027-1"

FIXTURE = [
    # (semester, course, units, score, letter, grade point, units x grade point)
    (FIRST, "CSC101", 3, 75, "A", "5.0", "15.0"),
    (FIRST, "MTH101", 4, 62, "B", "4.0", "16.0"),
    (FIRST, "GNS101", 2, 45, "D", "2.0", "4.0"),
    (SECOND, "CSC102", 3, 55, "C", "3.0", "9.0"),
    (SECOND, "MTH102", 4, 38, "F", "0.0", "0.0"),
    (SECOND, "PHY102", 3, 70, "A", "5.0", "15.0"),
    (THIRD, "MTH102", 4, 58, "C", "3.0", "12.0"),  # carry-over: the retake
    (THIRD, "CSC201", 3, 49, "D", "2.0", "6.0"),
]

EXPECTED_SEMESTER_GPA = {
    FIRST: Decimal("3.89"),  # 35.0 / 9  = 3.888...
    SECOND: Decimal("2.40"),  # 24.0 / 10 = 2.4
    THIRD: Decimal("2.57"),  # 18.0 / 7  = 2.571...
}
EXPECTED_TOTAL_UNITS = 26  # 9 + 10 + 7
EXPECTED_QUALITY_POINTS = Decimal("77.0")  # 35.0 + 24.0 + 18.0
EXPECTED_CGPA = Decimal("2.96")  # 77.0 / 26 = 2.9615...


def a_line(semester: str, course: str, units: int, score: int) -> CourseGrade:
    return CourseGrade.award(
        course_id=course,
        semester_id=semester,
        score=score,
        credit_units=units,
        scale=LASU_GRADING_SCALE,
    )


@pytest.fixture
def transcript() -> Transcript:
    """The fixture above, in the order the grades were submitted."""
    return Transcript(
        a_line(semester, course, units, score) for semester, course, units, score, *_ in FIXTURE
    )


# ---- the fixture, line by line ----


@pytest.mark.parametrize(
    ("semester", "course", "units", "score", "letter", "grade_point", "weighted"), FIXTURE
)
def test_each_line_grades_and_weighs_as_computed_by_hand(
    semester: str,
    course: str,
    units: int,
    score: int,
    letter: str,
    grade_point: str,
    weighted: str,
) -> None:
    line = a_line(semester, course, units, score)
    assert line.letter == letter
    assert line.grade_point == Decimal(grade_point)
    assert line.quality_points == Decimal(weighted)


# ---- the averages ----


@pytest.mark.parametrize(("semester", "expected"), list(EXPECTED_SEMESTER_GPA.items()))
def test_semester_gpa_matches_the_hand_computed_figure(
    transcript: Transcript, semester: str, expected: Decimal
) -> None:
    assert transcript.semester_gpa(semester) == expected


def test_cgpa_over_three_semesters_matches_the_hand_computed_figure(
    transcript: Transcript,
) -> None:
    assert transcript.total_units == EXPECTED_TOTAL_UNITS
    assert transcript.total_quality_points == EXPECTED_QUALITY_POINTS
    assert transcript.cgpa == EXPECTED_CGPA


def test_cgpa_is_not_the_average_of_the_semester_gpas(transcript: Transcript) -> None:
    """A weighted average over every unit, not a mean of three numbers.

    The two differ here — (3.89 + 2.40 + 2.57) / 3 is 2.95 — because the semesters carry
    different loads. Worth pinning: averaging the averages is the commonest way this gets
    written wrong, and it is wrong by a margin small enough to survive review.
    """
    mean_of_gpas = sum(EXPECTED_SEMESTER_GPA.values(), Decimal(0)) / 3
    assert round(mean_of_gpas, 2) == Decimal("2.95")
    assert transcript.cgpa == Decimal("2.96")


def test_cgpa_does_not_depend_on_the_order_grades_arrived_in(transcript: Transcript) -> None:
    """A sum does not care what order it is taken in.

    Which is why "CGPA over multiple semesters" is answerable without knowing which
    semester came first — and why this context does not need the session that
    ``GradeSubmitted`` does not carry.
    """
    reversed_arrival = Transcript(reversed(transcript.grades))
    assert reversed_arrival.cgpa == transcript.cgpa


# ---- carry-over: the confirmed rule ----


def test_both_attempts_at_a_carried_over_course_count_towards_the_cgpa(
    transcript: Transcript,
) -> None:
    """Confirmed with a human: every attempt is a line and every line counts.

    Dropping the failed attempt would leave 22 units and 77.0 points — a CGPA of 3.50
    instead of 2.96. The difference between the two rules is a whole grade point, which is
    why it was asked rather than assumed.
    """
    attempts = [line for line in transcript.grades if line.course_id == "MTH102"]
    assert [(line.semester_id, line.score, line.letter) for line in attempts] == [
        (SECOND, 38, "F"),
        (THIRD, 58, "C"),
    ]

    without_the_failure = Transcript(
        line for line in transcript.grades if line not in (attempts[0],)
    )
    assert without_the_failure.cgpa == Decimal("3.50")
    assert transcript.cgpa == Decimal("2.96")


def test_a_course_failed_then_passed_counts_as_passed(transcript: Transcript) -> None:
    """The prerequisite question and the CGPA question have different answers about MTH102."""
    assert "MTH102" in transcript.passed_course_ids


def test_passed_course_ids_holds_every_course_passed_at_least_once(
    transcript: Transcript,
) -> None:
    assert transcript.passed_course_ids == frozenset(
        {"CSC101", "MTH101", "GNS101", "CSC102", "PHY102", "MTH102", "CSC201"}
    )


def test_a_course_only_ever_failed_is_not_passed() -> None:
    failed_twice = Transcript([a_line(FIRST, "CHM101", 3, 30), a_line(SECOND, "CHM101", 3, 39)])
    assert failed_twice.passed_course_ids == frozenset()
    assert failed_twice.cgpa == Decimal("0.00")


# ---- semesters ----


def test_semesters_are_ordered_by_first_appearance(transcript: Transcript) -> None:
    """Arrival order, because ``semester_id`` is Faculty & Department's opaque key.

    Parsing an ordinal or a year out of it would be this context inventing a calendar it
    does not own.
    """
    assert transcript.semester_ids == (FIRST, SECOND, THIRD)


def test_semester_gpas_are_keyed_by_semester_in_that_same_order(
    transcript: Transcript,
) -> None:
    assert list(transcript.semester_gpas()) == [FIRST, SECOND, THIRD]
    assert transcript.semester_gpas() == EXPECTED_SEMESTER_GPA


def test_for_semester_returns_only_that_semesters_lines(transcript: Transcript) -> None:
    assert [line.course_id for line in transcript.for_semester(FIRST)] == [
        "CSC101",
        "MTH101",
        "GNS101",
    ]


def test_asking_for_the_gpa_of_a_semester_nobody_sat_is_refused(
    transcript: Transcript,
) -> None:
    """``0.00`` would be indistinguishable from a semester sat and failed entirely."""
    with pytest.raises(GradeNotRecordedError, match="sem-2028-1"):
        transcript.semester_gpa("sem-2028-1")


def test_a_blank_semester_id_is_refused(transcript: Transcript) -> None:
    with pytest.raises(MissingIdentifierError):
        transcript.for_semester("   ")


# ---- shape ----


def test_an_empty_transcript_averages_to_zero_rather_than_dividing_by_zero() -> None:
    """No persisted record is ever empty; this is an object mid-construction, not a student."""
    empty = Transcript([])
    assert empty.is_empty
    assert empty.cgpa == Decimal("0.00")
    assert empty.total_units == 0
    assert empty.semester_ids == ()


def test_the_lines_come_back_as_a_tuple_callers_cannot_write_into(
    transcript: Transcript,
) -> None:
    assert isinstance(transcript.grades, tuple)
    assert len(transcript) == len(FIXTURE)


def test_a_transcript_is_made_of_course_grades() -> None:
    with pytest.raises(TypeError):
        Transcript([{"course_id": "CSC101", "score": 75}])  # type: ignore[list-item]


def test_averages_are_decimals_rather_than_floats(transcript: Transcript) -> None:
    """A figure that prints as 2.9599999999999995 cannot be checked by hand."""
    assert isinstance(transcript.cgpa, Decimal)
    assert isinstance(transcript.semester_gpa(FIRST), Decimal)
    assert str(transcript.cgpa) == "2.96"


@pytest.mark.parametrize(
    ("scores_and_units", "expected"),
    [
        # 21.0 / 8 = 2.625 -> 2.63. Half up, not banker's rounding, which would give 2.62.
        ([(70, 3), (50, 2), (39, 3)], Decimal("2.63")),
        ([(75, 3)], Decimal("5.00")),
        ([(39, 3)], Decimal("0.00")),
    ],
)
def test_averages_round_half_up_to_two_places(
    scores_and_units: list[tuple[int, int]], expected: Decimal
) -> None:
    lines = [
        a_line(FIRST, f"CRS{index}", units, score)
        for index, (score, units) in enumerate(scores_and_units)
    ]
    assert Transcript(lines).cgpa == expected
