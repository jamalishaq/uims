"""The ``AcademicRecord`` aggregate, and the invariant it exists to hold.

The build playbook's Phase 4.2 asks that "direct grade mutation is impossible", and most of
this module is that one claim attacked from every angle available to a caller: assigning to
a field, writing through the collection the record hands back, re-recording a different
mark, replaying the same mark, correcting a grade without saying why. The only door that
opens is :meth:`AcademicRecord.correct_grade`, and it asks for a reason and a name.

Zero infrastructure, per CLAUDE.md section 2: records are built directly and asserted on. A
domain test that needed a repository would be evidence that logic had leaked outward.
"""

import dataclasses
from decimal import Decimal

import pytest

from academic_records.domain import (
    LASU_GRADING_SCALE,
    AcademicRecord,
    CourseGrade,
    GradeAlreadyRecordedError,
    GradeCorrection,
    GradeNotRecordedError,
    InvalidCorrectionError,
    InvalidCreditUnitsError,
    InvalidScoreError,
    MissingIdentifierError,
    Standing,
)

STUDENT_ID = "stu-2026-0001"
COURSE_ID = "CSC101"
SEMESTER_ID = "sem-2026-1"
OTHER_SEMESTER_ID = "sem-2027-1"


@pytest.fixture
def record() -> AcademicRecord:
    """A record with one line: CSC101, 3 units, 75 — an A worth 5.0."""
    record = AcademicRecord.open(STUDENT_ID)
    record.record_grade(course_id=COURSE_ID, semester_id=SEMESTER_ID, score=75, credit_units=3)
    return record


# ---- recording ----


def test_a_record_opens_with_nothing_on_it() -> None:
    """Opened and graded in the same breath by the use case; empty is a moment, not a state."""
    opened = AcademicRecord.open(STUDENT_ID)
    assert opened.student_id == STUDENT_ID
    assert opened.grades == ()
    assert opened.corrections == ()


def test_recording_a_grade_produces_a_line_graded_on_the_records_scale(
    record: AcademicRecord,
) -> None:
    (line,) = record.grades
    assert (line.course_id, line.semester_id, line.score) == (COURSE_ID, SEMESTER_ID, 75)
    assert (line.letter, line.grade_point) == ("A", Decimal("5.0"))
    assert line.credit_units == 3
    assert line.is_pass


def test_the_same_course_in_a_different_semester_is_a_separate_attempt(
    record: AcademicRecord,
) -> None:
    """Which is the confirmed carry-over rule, needing no code: the key includes the semester."""
    record.record_grade(
        course_id=COURSE_ID, semester_id=OTHER_SEMESTER_ID, score=55, credit_units=3
    )
    assert [(line.semester_id, line.score) for line in record.grades] == [
        (SEMESTER_ID, 75),
        (OTHER_SEMESTER_ID, 55),
    ]
    assert record.cgpa == Decimal("4.00")  # (15.0 + 9.0) / 6


def test_grade_for_finds_a_line_by_course_and_semester(record: AcademicRecord) -> None:
    assert record.grade_for(COURSE_ID, SEMESTER_ID) is not None
    assert record.has_grade_for(COURSE_ID, SEMESTER_ID)


def test_grade_for_answers_none_for_a_course_the_student_never_sat(
    record: AcademicRecord,
) -> None:
    """``None`` is an answer, not a failure: most courses a student has not sat."""
    assert record.grade_for("PHY999", SEMESTER_ID) is None
    assert not record.has_grade_for(COURSE_ID, OTHER_SEMESTER_ID)


@pytest.mark.parametrize("score", [-1, 101, 75.0, "75", True])
def test_a_grade_with_an_impossible_score_cannot_be_recorded(score: object) -> None:
    with pytest.raises(InvalidScoreError):
        AcademicRecord.open(STUDENT_ID).record_grade(
            course_id=COURSE_ID, semester_id=SEMESTER_ID, score=score, credit_units=3
        )


@pytest.mark.parametrize("units", [0, -3, 3.0, True])
def test_a_grade_with_impossible_credit_units_cannot_be_recorded(units: object) -> None:
    """Zero units would sit on a transcript moving neither the numerator nor the denominator."""
    with pytest.raises(InvalidCreditUnitsError):
        AcademicRecord.open(STUDENT_ID).record_grade(
            course_id=COURSE_ID, semester_id=SEMESTER_ID, score=75, credit_units=units
        )


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_grade_without_a_course_or_semester_cannot_be_recorded(blank: str) -> None:
    record = AcademicRecord.open(STUDENT_ID)
    with pytest.raises(MissingIdentifierError):
        record.record_grade(course_id=blank, semester_id=SEMESTER_ID, score=75, credit_units=3)
    with pytest.raises(MissingIdentifierError):
        record.record_grade(course_id=COURSE_ID, semester_id=blank, score=75, credit_units=3)


def test_a_record_cannot_be_opened_without_a_student() -> None:
    with pytest.raises(MissingIdentifierError):
        AcademicRecord.open("  ")


# ---- direct mutation is impossible ----


def test_a_transcript_line_is_frozen(record: AcademicRecord) -> None:
    """The first of the three locks: a line cannot be edited at all, by anybody."""
    (line,) = record.grades
    with pytest.raises(dataclasses.FrozenInstanceError):
        line.score = 30  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        line.grade_point = Decimal("0.0")  # type: ignore[misc]


def test_a_line_cannot_be_built_with_a_letter_that_disagrees_with_its_score() -> None:
    """Derived at construction from the scale, so ``75`` and ``F`` cannot coexist.

    ``CourseGrade`` has a plain constructor, as every dataclass does — but the constructor
    anything outside the module uses is :meth:`CourseGrade.award`, and it is the scale that
    fills in the letter and the point.
    """
    awarded = CourseGrade.award(
        course_id=COURSE_ID,
        semester_id=SEMESTER_ID,
        score=75,
        credit_units=3,
        scale=LASU_GRADING_SCALE,
    )
    assert (awarded.letter, awarded.grade_point) == ("A", Decimal("5.0"))


def test_the_grades_collection_handed_out_is_a_copy(record: AcademicRecord) -> None:
    """The second lock: writing into what you were handed does not reach the record."""
    grades = record.grades
    assert isinstance(grades, tuple)

    with pytest.raises(AttributeError):
        grades.append(  # type: ignore[attr-defined]
            CourseGrade.award(
                course_id="PHY101",
                semester_id=SEMESTER_ID,
                score=30,
                credit_units=3,
                scale=LASU_GRADING_SCALE,
            )
        )
    assert len(record.grades) == 1


def test_the_corrections_collection_handed_out_is_a_copy(record: AcademicRecord) -> None:
    assert isinstance(record.corrections, tuple)


def test_re_recording_a_different_score_for_the_same_course_and_semester_is_refused(
    record: AcademicRecord,
) -> None:
    """The third lock, and the one that matters: a recorded grade is final."""
    with pytest.raises(GradeAlreadyRecordedError, match="administrative correction"):
        record.record_grade(course_id=COURSE_ID, semester_id=SEMESTER_ID, score=30, credit_units=3)
    assert record.grade_for(COURSE_ID, SEMESTER_ID).score == 75  # type: ignore[union-attr]


def test_the_refusal_names_both_scores_so_the_registry_can_see_what_was_attempted(
    record: AcademicRecord,
) -> None:
    with pytest.raises(GradeAlreadyRecordedError) as refused:
        record.record_grade(course_id=COURSE_ID, semester_id=SEMESTER_ID, score=30, credit_units=3)
    assert "75" in str(refused.value)
    assert "30" in str(refused.value)


def test_replaying_the_same_grade_is_a_no_op_rather_than_a_failure(
    record: AcademicRecord,
) -> None:
    """At-least-once delivery is normal, and a replay must not read as an incident."""
    replayed = record.record_grade(
        course_id=COURSE_ID, semester_id=SEMESTER_ID, score=75, credit_units=3
    )
    assert replayed == record.grades[0]
    assert len(record.grades) == 1
    assert record.corrections == ()


def test_a_replay_carrying_different_credit_units_does_not_re_weight_the_line(
    record: AcademicRecord,
) -> None:
    """The snapshot holds. A course re-valued in the catalog does not rewrite the transcript."""
    replayed = record.record_grade(
        course_id=COURSE_ID, semester_id=SEMESTER_ID, score=75, credit_units=6
    )
    assert replayed.credit_units == 3
    assert record.transcript().total_units == 3


# ---- correction: the one door that opens ----


def test_correcting_a_grade_replaces_the_line_and_leaves_an_audit_entry(
    record: AcademicRecord,
) -> None:
    correction = record.correct_grade(
        course_id=COURSE_ID,
        semester_id=SEMESTER_ID,
        corrected_score=55,
        reason="script re-marked after appeal",
        authorized_by="Registrar A. Bello",
    )

    assert isinstance(correction, GradeCorrection)
    assert (correction.previous_score, correction.corrected_score) == (75, 55)
    assert correction.reason == "script re-marked after appeal"
    assert correction.authorized_by == "Registrar A. Bello"
    assert record.corrections == (correction,)


def test_a_correction_re_derives_the_letter_and_the_grade_point(
    record: AcademicRecord,
) -> None:
    """A correction cannot smuggle in a grade the scale does not award."""
    record.correct_grade(
        course_id=COURSE_ID,
        semester_id=SEMESTER_ID,
        corrected_score=55,
        reason="re-marked",
        authorized_by="Registrar",
    )
    (line,) = record.grades
    assert (line.score, line.letter, line.grade_point) == (55, "C", Decimal("3.0"))


def test_a_correction_moves_the_cgpa_and_can_move_the_standing() -> None:
    """Which is the reason anybody corrects a grade, and so the thing worth pinning."""
    record = AcademicRecord.open(STUDENT_ID)
    record.record_grade(course_id=COURSE_ID, semester_id=SEMESTER_ID, score=30, credit_units=3)
    assert record.cgpa == Decimal("0.00")
    assert record.standing is Standing.PROBATION

    record.correct_grade(
        course_id=COURSE_ID,
        semester_id=SEMESTER_ID,
        corrected_score=62,
        reason="marks transposed at entry",
        authorized_by="HOD",
    )
    assert record.cgpa == Decimal("4.00")
    assert record.standing is Standing.GOOD_STANDING


def test_a_correction_keeps_the_lines_position_in_the_transcript(
    record: AcademicRecord,
) -> None:
    """A correction fixes a mark; it does not move the course to the end of the record."""
    record.record_grade(course_id="MTH101", semester_id=SEMESTER_ID, score=62, credit_units=4)
    record.correct_grade(
        course_id=COURSE_ID,
        semester_id=SEMESTER_ID,
        corrected_score=55,
        reason="re-marked",
        authorized_by="Registrar",
    )
    assert [line.course_id for line in record.grades] == [COURSE_ID, "MTH101"]


def test_a_correction_carries_the_credit_units_of_the_line_it_replaces(
    record: AcademicRecord,
) -> None:
    """What is being fixed is the mark. Re-weighting a semester is not a correction."""
    record.correct_grade(
        course_id=COURSE_ID,
        semester_id=SEMESTER_ID,
        corrected_score=55,
        reason="re-marked",
        authorized_by="Registrar",
    )
    assert record.grades[0].credit_units == 3


def test_correcting_a_grade_that_was_never_recorded_is_refused(
    record: AcademicRecord,
) -> None:
    with pytest.raises(GradeNotRecordedError, match="nothing to correct"):
        record.correct_grade(
            course_id="PHY999",
            semester_id=SEMESTER_ID,
            corrected_score=55,
            reason="re-marked",
            authorized_by="Registrar",
        )


@pytest.mark.parametrize(("reason", "authorized_by"), [("", "Registrar"), ("re-marked", "  ")])
def test_a_correction_without_a_reason_or_an_authorizer_is_refused(
    record: AcademicRecord, reason: str, authorized_by: str
) -> None:
    """The audit trail is the point. A blank reason is indistinguishable from a mistake."""
    with pytest.raises(InvalidCorrectionError, match="reason"):
        record.correct_grade(
            course_id=COURSE_ID,
            semester_id=SEMESTER_ID,
            corrected_score=55,
            reason=reason,
            authorized_by=authorized_by,
        )
    assert record.grades[0].score == 75
    assert record.corrections == ()


def test_a_correction_that_changes_nothing_is_refused(record: AcademicRecord) -> None:
    """It would leave an audit entry describing an event that did not happen."""
    with pytest.raises(InvalidCorrectionError, match="already recorded"):
        record.correct_grade(
            course_id=COURSE_ID,
            semester_id=SEMESTER_ID,
            corrected_score=75,
            reason="re-marked",
            authorized_by="Registrar",
        )
    assert record.corrections == ()


def test_a_correction_to_an_impossible_score_is_refused(record: AcademicRecord) -> None:
    with pytest.raises(InvalidScoreError):
        record.correct_grade(
            course_id=COURSE_ID,
            semester_id=SEMESTER_ID,
            corrected_score=140,
            reason="re-marked",
            authorized_by="Registrar",
        )


def test_a_corrected_grade_can_be_corrected_again_and_both_acts_are_kept(
    record: AcademicRecord,
) -> None:
    """Every correction is history. The second does not overwrite the record of the first."""
    record.correct_grade(
        course_id=COURSE_ID,
        semester_id=SEMESTER_ID,
        corrected_score=55,
        reason="re-marked after appeal",
        authorized_by="Registrar",
    )
    record.correct_grade(
        course_id=COURSE_ID,
        semester_id=SEMESTER_ID,
        corrected_score=62,
        reason="appeal upheld at senate",
        authorized_by="Senate",
    )
    assert [(c.previous_score, c.corrected_score) for c in record.corrections] == [
        (75, 55),
        (55, 62),
    ]
    assert record.grades[0].score == 62


def test_a_correction_entry_is_frozen(record: AcademicRecord) -> None:
    correction = record.correct_grade(
        course_id=COURSE_ID,
        semester_id=SEMESTER_ID,
        corrected_score=55,
        reason="re-marked",
        authorized_by="Registrar",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        correction.reason = "something else"  # type: ignore[misc]


# ---- the record answers the questions the rest of the university asks ----


def test_a_record_reports_its_own_averages_standing_and_passes(
    record: AcademicRecord,
) -> None:
    record.record_grade(course_id="MTH101", semester_id=OTHER_SEMESTER_ID, score=30, credit_units=3)
    assert record.cgpa == Decimal("2.50")  # (15.0 + 0.0) / 6
    assert record.semester_gpa(SEMESTER_ID) == Decimal("5.00")
    assert record.semester_gpa(OTHER_SEMESTER_ID) == Decimal("0.00")
    assert record.standing is Standing.GOOD_STANDING
    assert record.passed_course_ids == frozenset({COURSE_ID})


def test_the_averages_are_derived_on_read_rather_than_stored(
    record: AcademicRecord,
) -> None:
    """No cached figure, so nothing can fall out of step and no job has to run."""
    assert record.cgpa == Decimal("5.00")
    record.record_grade(course_id="MTH101", semester_id=SEMESTER_ID, score=30, credit_units=3)
    assert record.cgpa == Decimal("2.50")
