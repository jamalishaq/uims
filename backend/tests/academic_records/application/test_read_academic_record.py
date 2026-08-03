"""``ReadAcademicRecord``: the surface the rest of the university reads this context through.

In particular it is what the adapter behind Enrollment's ``StudentAcademicStandingPort``
will call once Phase 6 replaces that context's hand-fed stub, so two of the assertions here
are about the *shape* of what comes back rather than its values: passes and not letters, a
standing and not a number. Both translations that adapter's docstring promises happen on
this side of the boundary.
"""

from decimal import Decimal

import pytest

from academic_records.adapters.outbound import InMemoryCourseCreditAdapter
from academic_records.application import (
    AcademicRecordNotFoundError,
    ReadAcademicRecord,
    RecordSubmittedGrade,
    RecordSubmittedGradeCommand,
)
from academic_records.domain import Standing

STUDENT_ID = "stu-2026-0001"
FIRST = "sem-2026-1"
SECOND = "sem-2027-1"


@pytest.fixture(autouse=True)
async def graded(
    courses: InMemoryCourseCreditAdapter, record_submitted_grade: RecordSubmittedGrade
) -> None:
    """CSC101 failed at 30 and carried over, passed at 55; MTH101 passed at 62."""
    courses.register("CSC101", credit_units=3)
    courses.register("MTH101", credit_units=4)
    for course_id, semester_id, score in [
        ("CSC101", FIRST, 30),
        ("MTH101", FIRST, 62),
        ("CSC101", SECOND, 55),
    ]:
        await record_submitted_grade.execute(
            RecordSubmittedGradeCommand(
                student_id=STUDENT_ID,
                course_id=course_id,
                semester_id=semester_id,
                score=score,
            )
        )


async def test_the_view_carries_the_averages_and_the_standing(
    read_academic_record: ReadAcademicRecord,
) -> None:
    view = await read_academic_record.execute(STUDENT_ID)

    assert view.student_id == STUDENT_ID
    assert view.cgpa == Decimal("2.50")  # (0.0 + 16.0 + 9.0) / 10
    assert view.total_units == 10
    assert view.standing is Standing.GOOD_STANDING
    assert view.semester_gpas == {FIRST: Decimal("2.29"), SECOND: Decimal("3.00")}


async def test_the_view_answers_in_passes_rather_than_letters(
    read_academic_record: ReadAcademicRecord,
) -> None:
    """The grades-to-passes translation happens here, on this side of the boundary.

    A prerequisite rule written against letter grades would be Enrollment quietly acquiring
    an opinion about what a pass is.
    """
    view = await read_academic_record.execute(STUDENT_ID)
    assert view.passed_course_ids == frozenset({"CSC101", "MTH101"})


async def test_a_carried_over_course_is_passed_while_both_attempts_still_count(
    read_academic_record: ReadAcademicRecord,
) -> None:
    view = await read_academic_record.execute(STUDENT_ID)
    assert "CSC101" in view.passed_course_ids
    assert len([line for line in view.grades if line.course_id == "CSC101"]) == 2


async def test_the_view_is_a_dto_rather_than_the_aggregate(
    read_academic_record: ReadAcademicRecord,
) -> None:
    """A read path that can write is a read path somebody will eventually write through."""
    view = await read_academic_record.execute(STUDENT_ID)
    assert not hasattr(view, "record_grade")
    assert not hasattr(view, "correct_grade")
    assert isinstance(view.grades, tuple)


async def test_reading_a_student_nobody_has_graded_is_an_error(
    read_academic_record: ReadAcademicRecord,
) -> None:
    with pytest.raises(AcademicRecordNotFoundError, match="stu-nobody"):
        await read_academic_record.execute("stu-nobody")


async def test_find_answers_none_for_a_student_nobody_has_graded(
    read_academic_record: ReadAcademicRecord,
) -> None:
    """The form a port adapter wants: a fresher is not a refusal.

    Enrollment reads ``None`` as ``AcademicStanding.unrecorded``, and an exception would put
    the first registration of every student's life through an error handler.
    """
    assert await read_academic_record.find("stu-nobody") is None
    assert await read_academic_record.find(STUDENT_ID) is not None
