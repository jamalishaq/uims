"""The in-memory adapters, against the contracts their ports state.

Written against the *port* semantics rather than the dict behind them, so the same
assertions carry over when Phase 6 puts Postgres behind the repository and a Course Catalog
client behind the credit adapter.
"""

import pytest

from academic_records.adapters.outbound import (
    InMemoryAcademicRecordRepository,
    InMemoryCourseCreditAdapter,
)
from academic_records.domain import (
    AcademicRecord,
    CourseCredits,
    InvalidCreditUnitsError,
    MissingIdentifierError,
)
from academic_records.ports import (
    AcademicRecordRepositoryPort,
    AggregateNotFoundError,
    CourseCreditPort,
    DuplicateAggregateError,
)

STUDENT_ID = "stu-2026-0001"


def a_record(student_id: str = STUDENT_ID) -> AcademicRecord:
    record = AcademicRecord.open(student_id)
    record.record_grade(course_id="CSC101", semester_id="sem-2026-1", score=75, credit_units=3)
    return record


# ---- the repository ----


def test_a_stored_record_comes_back(records: AcademicRecordRepositoryPort) -> None:
    records.add(a_record())
    stored = records.get(STUDENT_ID)
    assert stored is not None
    assert stored.student_id == STUDENT_ID


def test_a_student_nobody_has_graded_answers_none(
    records: AcademicRecordRepositoryPort,
) -> None:
    """Absence is a normal answer, and here it is the usual one."""
    assert records.get("stu-nobody") is None


def test_adding_a_second_record_for_the_same_student_is_refused(
    records: AcademicRecordRepositoryPort,
) -> None:
    """One record per student. Under Postgres this is the unique constraint on the key."""
    records.add(a_record())
    with pytest.raises(DuplicateAggregateError, match=STUDENT_ID):
        records.add(a_record())


def test_saving_a_record_that_was_never_added_is_refused(
    records: AcademicRecordRepositoryPort,
) -> None:
    with pytest.raises(AggregateNotFoundError, match=STUDENT_ID):
        records.save(a_record())


def test_saving_persists_a_change(records: AcademicRecordRepositoryPort) -> None:
    record = a_record()
    records.add(record)
    record.record_grade(course_id="MTH101", semester_id="sem-2026-1", score=62, credit_units=4)
    records.save(record)

    stored = records.get(STUDENT_ID)
    assert stored is not None
    assert len(stored.grades) == 2


def test_records_are_kept_apart_by_student(records: AcademicRecordRepositoryPort) -> None:
    records.add(a_record("stu-a"))
    records.add(a_record("stu-b"))
    assert records.get("stu-a").student_id == "stu-a"  # type: ignore[union-attr]
    assert records.get("stu-b").student_id == "stu-b"  # type: ignore[union-attr]


def test_the_repository_offers_no_way_to_delete_a_record(
    records: AcademicRecordRepositoryPort,
) -> None:
    """A transcript is asked for decades after the student leaves. Nothing deletes one."""
    assert not hasattr(records, "remove")
    assert not hasattr(records, "delete")


# ---- the course-credit adapter ----


def test_a_registered_course_answers_its_units(courses: InMemoryCourseCreditAdapter) -> None:
    courses.register("CSC101", credit_units=3)
    assert courses.credits_for("CSC101") == CourseCredits(course_id="CSC101", credit_units=3)


def test_a_course_the_catalog_does_not_know_answers_none(
    courses: InMemoryCourseCreditAdapter,
) -> None:
    assert courses.credits_for("PHY999") is None


def test_re_registering_a_course_re_values_it(courses: InMemoryCourseCreditAdapter) -> None:
    """A catalog amendment. It changes *future* lines only — recorded ones hold a snapshot."""
    courses.register("CSC101", credit_units=3)
    courses.register("CSC101", credit_units=4)
    assert courses.credits_for("CSC101").credit_units == 4  # type: ignore[union-attr]


@pytest.mark.parametrize("units", [0, -1, 3.5, True])
def test_a_course_registered_with_nonsense_units_fails_at_registration(
    courses: InMemoryCourseCreditAdapter, units: object
) -> None:
    """Here, rather than at the moment somebody's grade is being recorded."""
    with pytest.raises(InvalidCreditUnitsError):
        courses.register("CSC101", credit_units=units)  # type: ignore[arg-type]


def test_a_course_registered_without_an_id_is_refused(
    courses: InMemoryCourseCreditAdapter,
) -> None:
    with pytest.raises(MissingIdentifierError):
        courses.register("  ", credit_units=3)


def test_the_adapter_carries_no_retirement_flag(courses: InMemoryCourseCreditAdapter) -> None:
    """Deliberate. A retired course must keep resolving here: transcripts refer to courses
    no longer taught, which is why Course Catalog retires them instead of deleting them.
    """
    courses.register("CSC101", credit_units=3)
    facts = courses.credits_for("CSC101")
    assert facts is not None
    assert not hasattr(facts, "is_active")
    assert not hasattr(courses, "retire")


def test_the_adapter_is_a_course_credit_port(courses: InMemoryCourseCreditAdapter) -> None:
    assert isinstance(courses, CourseCreditPort)


def test_the_repository_is_an_academic_record_repository_port(
    records: AcademicRecordRepositoryPort,
) -> None:
    assert isinstance(records, InMemoryAcademicRecordRepository)
    assert isinstance(records, AcademicRecordRepositoryPort)
