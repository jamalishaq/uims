"""The ``RecordSubmittedGrade`` use case, driven through its ports.

Three things are under test that the domain tests cannot see: that a student's first grade
opens a record rather than failing, that credit units come from Course Catalog rather than
from the caller, and that a course of unknown worth is refused instead of guessed at.
"""

from decimal import Decimal

import pytest

from academic_records.adapters.outbound import InMemoryCourseCreditAdapter
from academic_records.application import (
    CourseCreditsUnavailableError,
    RecordSubmittedGrade,
    RecordSubmittedGradeCommand,
)
from academic_records.domain import GradeAlreadyRecordedError, Standing
from academic_records.ports import AcademicRecordRepositoryPort

STUDENT_ID = "stu-2026-0001"
COURSE_ID = "CSC101"
SEMESTER_ID = "sem-2026-1"


def a_command(**overrides: object) -> RecordSubmittedGradeCommand:
    fields: dict[str, object] = {
        "student_id": STUDENT_ID,
        "course_id": COURSE_ID,
        "semester_id": SEMESTER_ID,
        "score": 75,
    }
    fields.update(overrides)
    return RecordSubmittedGradeCommand(**fields)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def catalog(courses: InMemoryCourseCreditAdapter) -> InMemoryCourseCreditAdapter:
    """What Course Catalog would answer: CSC101 is worth 3 units, MTH101 four."""
    courses.register(COURSE_ID, credit_units=3)
    courses.register("MTH101", credit_units=4)
    return courses


def test_a_students_first_grade_opens_their_record(
    record_submitted_grade: RecordSubmittedGrade, records: AcademicRecordRepositoryPort
) -> None:
    """A missing record is a fresher, not a failure — grade submission is the trigger."""
    assert records.get(STUDENT_ID) is None

    result = record_submitted_grade.execute(a_command())

    stored = records.get(STUDENT_ID)
    assert stored is not None
    assert stored.student_id == STUDENT_ID
    assert result.was_already_recorded is False
    assert result.grade.score == 75


def test_the_line_is_weighed_with_the_units_the_catalog_answered(
    record_submitted_grade: RecordSubmittedGrade, records: AcademicRecordRepositoryPort
) -> None:
    """Credit units are looked up, never taken from the caller: the command has no such field."""
    record_submitted_grade.execute(a_command())
    record_submitted_grade.execute(a_command(course_id="MTH101", score=62))

    stored = records.get(STUDENT_ID)
    assert stored is not None
    assert [line.credit_units for line in stored.grades] == [3, 4]
    assert stored.cgpa == Decimal("4.43")  # (15.0 + 16.0) / 7


def test_a_second_grade_is_added_to_the_record_that_already_exists(
    record_submitted_grade: RecordSubmittedGrade, records: AcademicRecordRepositoryPort
) -> None:
    record_submitted_grade.execute(a_command())
    result = record_submitted_grade.execute(a_command(course_id="MTH101", score=62))

    stored = records.get(STUDENT_ID)
    assert stored is not None
    assert len(stored.grades) == 2
    assert result.was_already_recorded is False


def test_a_grade_for_a_course_the_catalog_does_not_know_is_refused(
    record_submitted_grade: RecordSubmittedGrade, records: AcademicRecordRepositoryPort
) -> None:
    """Recording it at some default weight would misstate a CGPA with nothing to flag it."""
    with pytest.raises(CourseCreditsUnavailableError, match="PHY999"):
        record_submitted_grade.execute(a_command(course_id="PHY999"))
    assert records.get(STUDENT_ID) is None


def test_the_catalog_is_consulted_before_a_record_is_opened(
    record_submitted_grade: RecordSubmittedGrade, records: AcademicRecordRepositoryPort
) -> None:
    """A refused submission leaves no trace: no empty record for a student nobody graded."""
    with pytest.raises(CourseCreditsUnavailableError):
        record_submitted_grade.execute(a_command(course_id="PHY999"))
    with pytest.raises(CourseCreditsUnavailableError):
        record_submitted_grade.execute(a_command(course_id="PHY999", student_id="stu-other"))
    assert records.get("stu-other") is None


# ---- redelivery ----


def test_replaying_the_same_grade_leaves_exactly_one_line(
    record_submitted_grade: RecordSubmittedGrade, records: AcademicRecordRepositoryPort
) -> None:
    """A bus that guarantees at-least-once delivery will replay this. Twice is not an error."""
    record_submitted_grade.execute(a_command())
    replay = record_submitted_grade.execute(a_command())

    stored = records.get(STUDENT_ID)
    assert stored is not None
    assert len(stored.grades) == 1
    assert replay.was_already_recorded is True
    assert replay.grade.score == 75


def test_a_replay_does_not_move_the_cgpa(
    record_submitted_grade: RecordSubmittedGrade, records: AcademicRecordRepositoryPort
) -> None:
    record_submitted_grade.execute(a_command())
    before = records.get(STUDENT_ID).cgpa  # type: ignore[union-attr]
    record_submitted_grade.execute(a_command())
    assert records.get(STUDENT_ID).cgpa == before  # type: ignore[union-attr]


def test_a_different_score_for_a_course_already_graded_is_refused(
    record_submitted_grade: RecordSubmittedGrade, records: AcademicRecordRepositoryPort
) -> None:
    """Recorded grades are final. The domain error passes through untranslated."""
    record_submitted_grade.execute(a_command())

    with pytest.raises(GradeAlreadyRecordedError):
        record_submitted_grade.execute(a_command(score=30))

    stored = records.get(STUDENT_ID)
    assert stored is not None
    assert stored.grades[0].score == 75


def test_the_same_course_in_a_later_semester_is_a_carry_over_and_both_count(
    record_submitted_grade: RecordSubmittedGrade, records: AcademicRecordRepositoryPort
) -> None:
    """Confirmed rule: every attempt is a line and every line counts."""
    record_submitted_grade.execute(a_command(score=30))
    record_submitted_grade.execute(a_command(semester_id="sem-2027-1", score=55))

    stored = records.get(STUDENT_ID)
    assert stored is not None
    assert len(stored.grades) == 2
    assert stored.cgpa == Decimal("1.50")  # (0.0 + 9.0) / 6
    assert stored.passed_course_ids == frozenset({COURSE_ID})


# ---- what the record then says about the student ----


def test_a_failing_students_record_comes_out_on_probation(
    record_submitted_grade: RecordSubmittedGrade, records: AcademicRecordRepositoryPort
) -> None:
    record_submitted_grade.execute(a_command(score=42))
    record_submitted_grade.execute(a_command(course_id="MTH101", score=30))

    stored = records.get(STUDENT_ID)
    assert stored is not None
    assert stored.cgpa == Decimal("0.86")  # 6.0 / 7
    assert stored.standing is Standing.PROBATION


def test_two_students_get_two_records(
    record_submitted_grade: RecordSubmittedGrade, records: AcademicRecordRepositoryPort
) -> None:
    record_submitted_grade.execute(a_command())
    record_submitted_grade.execute(a_command(student_id="stu-2026-0002", score=30))

    assert records.get(STUDENT_ID).cgpa == Decimal("5.00")  # type: ignore[union-attr]
    assert records.get("stu-2026-0002").cgpa == Decimal("0.00")  # type: ignore[union-attr]
