"""The ``CorrectGrade`` use case: the only path by which a recorded grade ever changes.

The domain tests already establish that the aggregate refuses everything else. What is
under test here is the use case around it — that it loads the stored record rather than
trusting a caller, that it stores the result, and that it reports what the correction did
to the two numbers anybody corrects a grade for.
"""

from decimal import Decimal

import pytest

from academic_records.adapters.outbound import InMemoryCourseCreditAdapter
from academic_records.application import (
    AcademicRecordNotFoundError,
    CorrectGrade,
    CorrectGradeCommand,
    RecordSubmittedGrade,
    RecordSubmittedGradeCommand,
)
from academic_records.domain import (
    GradeNotRecordedError,
    InvalidCorrectionError,
    Standing,
)
from academic_records.ports import AcademicRecordRepositoryPort

STUDENT_ID = "stu-2026-0001"
COURSE_ID = "CSC101"
SEMESTER_ID = "sem-2026-1"


def a_command(**overrides: object) -> CorrectGradeCommand:
    fields: dict[str, object] = {
        "student_id": STUDENT_ID,
        "course_id": COURSE_ID,
        "semester_id": SEMESTER_ID,
        "corrected_score": 62,
        "reason": "script re-marked after appeal",
        "authorized_by": "Registrar A. Bello",
    }
    fields.update(overrides)
    return CorrectGradeCommand(**fields)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
async def graded(
    courses: InMemoryCourseCreditAdapter, record_submitted_grade: RecordSubmittedGrade
) -> None:
    """A student with one failed 3-unit course on their record: CSC101 at 30."""
    courses.register(COURSE_ID, credit_units=3)
    await record_submitted_grade.execute(
        RecordSubmittedGradeCommand(
            student_id=STUDENT_ID, course_id=COURSE_ID, semester_id=SEMESTER_ID, score=30
        )
    )


async def test_a_correction_changes_the_stored_grade(
    correct_grade: CorrectGrade, records: AcademicRecordRepositoryPort
) -> None:
    await correct_grade.execute(a_command())

    stored = await records.get(STUDENT_ID)
    assert stored is not None
    assert stored.grades[0].score == 62
    assert stored.grades[0].letter == "B"


async def test_a_correction_reports_the_cgpa_and_standing_it_produced(
    correct_grade: CorrectGrade,
) -> None:
    """The reason anyone corrects a grade, answered without a second round trip."""
    result = await correct_grade.execute(a_command())

    assert result.cgpa == Decimal("4.00")
    assert result.standing is Standing.GOOD_STANDING
    assert (result.correction.previous_score, result.correction.corrected_score) == (30, 62)


async def test_a_correction_can_move_a_student_off_probation(
    correct_grade: CorrectGrade, records: AcademicRecordRepositoryPort
) -> None:
    before = await records.get(STUDENT_ID)
    assert before is not None
    assert before.standing is Standing.PROBATION

    await correct_grade.execute(a_command())

    assert (await records.get(STUDENT_ID)).standing is Standing.GOOD_STANDING  # type: ignore[union-attr]


async def test_the_correction_is_kept_on_the_stored_record(
    correct_grade: CorrectGrade, records: AcademicRecordRepositoryPort
) -> None:
    """A corrected grade with no record of the correction is the thing this prevents."""
    await correct_grade.execute(a_command())

    stored = await records.get(STUDENT_ID)
    assert stored is not None
    (correction,) = stored.corrections
    assert correction.reason == "script re-marked after appeal"
    assert correction.authorized_by == "Registrar A. Bello"


async def test_correcting_a_student_with_no_record_is_refused(correct_grade: CorrectGrade) -> None:
    with pytest.raises(AcademicRecordNotFoundError, match="stu-nobody"):
        await correct_grade.execute(a_command(student_id="stu-nobody"))


async def test_correcting_a_course_the_record_does_not_hold_is_refused(
    correct_grade: CorrectGrade,
) -> None:
    with pytest.raises(GradeNotRecordedError):
        await correct_grade.execute(a_command(course_id="PHY999"))


@pytest.mark.parametrize(("reason", "authorized_by"), [("", "Registrar"), ("re-marked", " ")])
async def test_a_correction_without_a_reason_or_an_authorizer_is_refused(
    correct_grade: CorrectGrade,
    records: AcademicRecordRepositoryPort,
    reason: str,
    authorized_by: str,
) -> None:
    with pytest.raises(InvalidCorrectionError):
        await correct_grade.execute(a_command(reason=reason, authorized_by=authorized_by))
    assert (await records.get(STUDENT_ID)).grades[0].score == 30  # type: ignore[union-attr]


async def test_a_correction_that_changes_nothing_is_refused(correct_grade: CorrectGrade) -> None:
    with pytest.raises(InvalidCorrectionError, match="already recorded"):
        await correct_grade.execute(a_command(corrected_score=30))


async def test_the_use_case_loads_the_stored_record_rather_than_trusting_its_caller(
    correct_grade: CorrectGrade, records: AcademicRecordRepositoryPort
) -> None:
    """The command carries identifiers only — there is no way to hand it a record."""
    assert not hasattr(a_command(), "record")
    await correct_grade.execute(a_command())
    assert (await records.get(STUDENT_ID)).grades[0].score == 62  # type: ignore[union-attr]
