"""The in-memory adapters: store semantics, and the translations the query adapters own.

Two different things are tested here. The repositories are tested for the contract the
ports state — add/save/get and what each refuses — because Phase 6's Postgres adapters have
to satisfy the same one. The three query adapters are tested for their *translation*: that
what a caller registers in another context's terms comes back in ours.
"""

import pytest

from enrollment.adapters.outbound import (
    InMemoryCourseInfoAdapter,
    InMemoryCourseOfferingRepository,
    InMemoryEnrollmentRepository,
    InMemoryStudentAcademicStandingAdapter,
    StubFinancialClearanceAdapter,
)
from enrollment.domain import (
    AcademicStanding,
    CourseFacts,
    CourseOffering,
    Enrollment,
    InvalidCreditUnitsError,
    SemesterOrdinal,
    Standing,
    Term,
)
from enrollment.ports import AggregateNotFoundError, DuplicateAggregateError

STUDENT_ID = "stu-260591001"
OTHER_STUDENT_ID = "stu-260591002"
CSC101 = "crs-csc101"
CSC201 = "crs-csc201"

FIRST = Term(session_id="sess-2026", semester_id="sem-2026-1", ordinal=SemesterOrdinal.FIRST)
SECOND = Term(session_id="sess-2026", semester_id="sem-2026-2", ordinal=SemesterOrdinal.SECOND)


def an_enrollment(
    enrollment_id: str = "enr-0001",
    *,
    student_id: str = STUDENT_ID,
    course_id: str = CSC201,
    term: Term = FIRST,
    credit_units: int = 3,
) -> Enrollment:
    return Enrollment.register(
        enrollment_id=enrollment_id,
        student_id=student_id,
        course=CourseFacts(course_id=course_id, credit_units=credit_units),
        term=term,
    )


class TestEnrollmentRepository:
    def test_stores_and_returns_a_registration(self) -> None:
        repository = InMemoryEnrollmentRepository()
        repository.add(an_enrollment())
        stored = repository.get("enr-0001")
        assert stored is not None
        assert stored.course_id == CSC201

    def test_returns_none_for_an_id_nobody_stored(self) -> None:
        """Absence is an answer, not a failure."""
        assert InMemoryEnrollmentRepository().get("enr-nothing") is None

    def test_refuses_to_add_the_same_id_twice(self) -> None:
        repository = InMemoryEnrollmentRepository()
        repository.add(an_enrollment())
        with pytest.raises(DuplicateAggregateError):
            repository.add(an_enrollment())

    def test_refuses_to_save_something_never_added(self) -> None:
        with pytest.raises(AggregateNotFoundError):
            InMemoryEnrollmentRepository().save(an_enrollment())

    def test_lists_only_this_student_and_only_this_term(self) -> None:
        """The load a cap is measured against: one student, one term, nothing else."""
        repository = InMemoryEnrollmentRepository()
        repository.add(an_enrollment("enr-1"))
        repository.add(an_enrollment("enr-2", course_id=CSC101))
        repository.add(an_enrollment("enr-3", term=SECOND))
        repository.add(an_enrollment("enr-4", student_id=OTHER_STUDENT_ID))

        listed = repository.list_for_student_in_term(STUDENT_ID, FIRST)
        assert [enrollment.enrollment_id for enrollment in listed] == ["enr-1", "enr-2"]

    def test_lists_in_the_order_registered(self) -> None:
        repository = InMemoryEnrollmentRepository()
        repository.add(an_enrollment("enr-b", course_id=CSC201))
        repository.add(an_enrollment("enr-a", course_id=CSC101))
        listed = repository.list_for_student_in_term(STUDENT_ID, FIRST)
        assert [enrollment.enrollment_id for enrollment in listed] == ["enr-b", "enr-a"]

    def test_sees_a_previous_registration_in_any_term(self) -> None:
        """What makes a re-registration a carry-over: it happened before, somewhere."""
        repository = InMemoryEnrollmentRepository()
        repository.add(an_enrollment("enr-1", course_id=CSC201, term=FIRST))
        assert repository.has_registered_before(STUDENT_ID, CSC201)

    def test_does_not_confuse_one_student_history_with_another(self) -> None:
        repository = InMemoryEnrollmentRepository()
        repository.add(an_enrollment("enr-1", student_id=OTHER_STUDENT_ID))
        assert not repository.has_registered_before(STUDENT_ID, CSC201)


class TestCourseOfferingRepository:
    def test_stores_and_returns_an_offering(self) -> None:
        repository = InMemoryCourseOfferingRepository()
        repository.add(CourseOffering.open(CSC201, FIRST, capacity=40))
        offering = repository.get(CSC201, FIRST)
        assert offering is not None
        assert offering.capacity == 40

    def test_the_same_course_next_term_is_a_different_offering(self) -> None:
        """Identity is ``(course_id, term)``: seats do not carry over between semesters."""
        repository = InMemoryCourseOfferingRepository()
        repository.add(CourseOffering.open(CSC201, FIRST, capacity=40))
        repository.add(CourseOffering(CSC201, SECOND, 40, seats_taken=40))

        first = repository.get(CSC201, FIRST)
        second = repository.get(CSC201, SECOND)
        assert first is not None and second is not None
        assert (first.seats_taken, second.seats_taken) == (0, 40)

    def test_returns_none_for_a_course_not_run_this_term(self) -> None:
        repository = InMemoryCourseOfferingRepository()
        repository.add(CourseOffering.open(CSC201, FIRST, capacity=40))
        assert repository.get(CSC201, SECOND) is None

    def test_refuses_to_offer_the_same_course_twice_in_one_term(self) -> None:
        repository = InMemoryCourseOfferingRepository()
        repository.add(CourseOffering.open(CSC201, FIRST, capacity=40))
        with pytest.raises(DuplicateAggregateError):
            repository.add(CourseOffering.open(CSC201, FIRST, capacity=10))

    def test_refuses_to_save_an_offering_never_opened(self) -> None:
        with pytest.raises(AggregateNotFoundError):
            InMemoryCourseOfferingRepository().save(CourseOffering.open(CSC201, FIRST, capacity=40))

    def test_saves_a_claimed_seat(self) -> None:
        repository = InMemoryCourseOfferingRepository()
        repository.add(CourseOffering.open(CSC201, FIRST, capacity=40))
        offering = repository.get(CSC201, FIRST)
        assert offering is not None
        offering.claim_seat()
        repository.save(offering)

        reread = repository.get(CSC201, FIRST)
        assert reread is not None
        assert reread.seats_taken == 1


class TestCourseInfoAdapter:
    def test_answers_in_this_context_s_own_type(self) -> None:
        adapter = InMemoryCourseInfoAdapter()
        adapter.register(CSC201, credit_units=3, prerequisite_ids=(CSC101,))
        facts = adapter.course_for(CSC201)
        assert isinstance(facts, CourseFacts)
        assert (facts.credit_units, facts.prerequisite_ids) == (3, (CSC101,))
        assert facts.is_active

    def test_returns_none_for_a_course_the_catalog_does_not_hold(self) -> None:
        assert InMemoryCourseInfoAdapter().course_for("crs-nothing") is None

    def test_a_retired_course_stays_known_and_stops_being_registrable(self) -> None:
        """The distinction retirement exists to draw, and the one this adapter translates."""
        adapter = InMemoryCourseInfoAdapter()
        adapter.register(CSC201, credit_units=3)
        adapter.retire(CSC201)

        facts = adapter.course_for(CSC201)
        assert facts is not None
        assert not facts.is_active

    def test_rejects_nonsense_at_the_boundary_rather_than_at_registration_time(self) -> None:
        with pytest.raises(InvalidCreditUnitsError):
            InMemoryCourseInfoAdapter().register(CSC201, credit_units=0)


class TestStudentAcademicStandingAdapter:
    def test_answers_in_this_context_s_own_type(self) -> None:
        adapter = InMemoryStudentAcademicStandingAdapter()
        adapter.register(STUDENT_ID, passed_course_ids=(CSC101,))
        standing = adapter.standing_for(STUDENT_ID)
        assert isinstance(standing, AcademicStanding)
        assert standing.has_passed(CSC101)
        assert standing.standing is Standing.GOOD_STANDING

    def test_returns_none_for_a_student_academic_records_has_never_heard_of(self) -> None:
        """The common answer at the moment it matters most: a fresher's first registration."""
        assert InMemoryStudentAcademicStandingAdapter().standing_for("stu-fresher") is None

    def test_carries_probation_across_as_a_conclusion_not_a_number(self) -> None:
        adapter = InMemoryStudentAcademicStandingAdapter()
        adapter.register(STUDENT_ID, standing=Standing.PROBATION)
        standing = adapter.standing_for(STUDENT_ID)
        assert standing is not None
        assert standing.standing is Standing.PROBATION

    def test_no_grade_crosses_the_boundary(self) -> None:
        """What counts as a pass is Academic Records'; what arrives here is a set of ids."""
        adapter = InMemoryStudentAcademicStandingAdapter()
        adapter.register(STUDENT_ID, passed_course_ids=(CSC101,))
        standing = adapter.standing_for(STUDENT_ID)
        assert standing is not None
        assert standing.passed_course_ids == frozenset({CSC101})
        assert not hasattr(standing, "grades")


class TestStubFinancialClearanceAdapter:
    def test_clears_everyone_until_billing_exists(self) -> None:
        assert StubFinancialClearanceAdapter().is_cleared_for_registration(STUDENT_ID, FIRST)

    def test_a_denial_applies_to_one_student_in_one_term(self) -> None:
        adapter = StubFinancialClearanceAdapter()
        adapter.deny(STUDENT_ID, FIRST)

        assert not adapter.is_cleared_for_registration(STUDENT_ID, FIRST)
        assert adapter.is_cleared_for_registration(STUDENT_ID, SECOND)
        assert adapter.is_cleared_for_registration(OTHER_STUDENT_ID, FIRST)

    def test_a_denial_can_be_lifted(self) -> None:
        adapter = StubFinancialClearanceAdapter()
        adapter.deny(STUDENT_ID, FIRST)
        adapter.clear(STUDENT_ID, FIRST)
        assert adapter.is_cleared_for_registration(STUDENT_ID, FIRST)

    def test_answers_a_bare_boolean_and_nothing_about_money(self) -> None:
        """Enrollment only ever sees yes/no: no balance, no percentage, no fee."""
        answer = StubFinancialClearanceAdapter().is_cleared_for_registration(STUDENT_ID, FIRST)
        assert isinstance(answer, bool)
