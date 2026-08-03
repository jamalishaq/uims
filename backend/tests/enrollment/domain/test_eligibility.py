"""``EligibilityRule``: the judgement, tested with no infrastructure whatsoever.

This is where the three rules the build playbook names live — prerequisites passed, credit
load capped, capacity — plus the two that fall out of a student's record. Every one of them
is exercised here against plain value objects, which is the point: if any of these tests
needed a repository or a port, the judgement would have leaked out of the domain.

Each reason is tested alone, then several together, because collecting *all* the failures
rather than the first is a behaviour a student experiences directly — being turned away
twice for two things the university knew about at once.

A LASU-shaped cast: CSC201 is worth 3 units and requires CSC101.
"""

import pytest

from enrollment.domain import (
    AcademicStanding,
    CourseFacts,
    CourseOffering,
    CreditLoadPolicy,
    EligibilityReason,
    EligibilityRule,
    SemesterOrdinal,
    Standing,
    Term,
)

STUDENT_ID = "stu-260591001"
CSC101 = "crs-csc101"
CSC201 = "crs-csc201"
MTH101 = "crs-mth101"
TERM = Term(session_id="sess-2026", semester_id="sem-2026-1", ordinal=SemesterOrdinal.FIRST)

COURSE_WITH_PREREQUISITE = CourseFacts(course_id=CSC201, credit_units=3, prerequisite_ids=(CSC101,))
COURSE_WITHOUT_PREREQUISITE = CourseFacts(course_id=CSC101, credit_units=3)


def an_offering(course_id: str = CSC201, *, capacity: int = 40, taken: int = 0) -> CourseOffering:
    return CourseOffering(course_id, TERM, capacity, seats_taken=taken)


def a_standing(*passed: str, standing: Standing = Standing.GOOD_STANDING) -> AcademicStanding:
    return AcademicStanding(
        student_id=STUDENT_ID, passed_course_ids=frozenset(passed), standing=standing
    )


def unmet(
    *,
    course: CourseFacts = COURSE_WITH_PREREQUISITE,
    offering: CourseOffering | None = None,
    standing: AcademicStanding | None = None,
    current_load: int = 0,
    already_registered: bool = False,
    is_financially_cleared: bool = True,
    rule: EligibilityRule | None = None,
) -> tuple[EligibilityReason, ...]:
    """Run the rule over one proposed registration and return just the reasons."""
    failures = (rule or EligibilityRule()).unmet(
        course=course,
        offering=offering if offering is not None else an_offering(course.course_id),
        standing=standing if standing is not None else a_standing(CSC101),
        current_load=current_load,
        already_registered=already_registered,
        is_financially_cleared=is_financially_cleared,
    )
    return tuple(failure.reason for failure in failures)


class TestAPermittedRegistration:
    def test_nothing_is_unmet_when_everything_is_in_order(self) -> None:
        assert unmet() == ()

    def test_permits_agrees_with_unmet(self) -> None:
        """Defined in terms of each other: the rule cannot decide one thing and explain another."""
        rule = EligibilityRule()
        assert rule.permits(
            course=COURSE_WITH_PREREQUISITE,
            offering=an_offering(),
            standing=a_standing(CSC101),
            current_load=0,
            already_registered=False,
            is_financially_cleared=True,
        )
        assert not rule.permits(
            course=COURSE_WITH_PREREQUISITE,
            offering=an_offering(),
            standing=a_standing(),
            current_load=0,
            already_registered=False,
            is_financially_cleared=True,
        )

    def test_a_fresher_with_no_record_may_take_a_course_with_no_prerequisites(self) -> None:
        """The first registration of a student's life must be possible."""
        assert (
            unmet(
                course=COURSE_WITHOUT_PREREQUISITE,
                offering=an_offering(CSC101),
                standing=AcademicStanding.unrecorded(STUDENT_ID),
            )
            == ()
        )

    def test_a_subject_sat_that_the_course_never_asked_for_disqualifies_nobody(self) -> None:
        assert unmet(standing=a_standing(CSC101, MTH101)) == ()


class TestPrerequisites:
    def test_refuses_a_course_whose_prerequisite_was_never_passed(self) -> None:
        assert unmet(standing=a_standing()) == (EligibilityReason.PREREQUISITE_NOT_PASSED,)

    def test_names_every_missing_prerequisite_separately(self) -> None:
        """Two courses to go and find; a single 'prerequisites not met' names neither."""
        course = CourseFacts(course_id=CSC201, credit_units=3, prerequisite_ids=(CSC101, MTH101))
        failures = EligibilityRule().unmet(
            course=course,
            offering=an_offering(),
            standing=a_standing(),
            current_load=0,
            already_registered=False,
            is_financially_cleared=True,
        )
        assert [failure.reason for failure in failures] == [
            EligibilityReason.PREREQUISITE_NOT_PASSED
        ] * 2
        assert CSC101 in failures[0].detail
        assert MTH101 in failures[1].detail

    def test_a_partially_met_requirement_is_still_unmet(self) -> None:
        course = CourseFacts(course_id=CSC201, credit_units=3, prerequisite_ids=(CSC101, MTH101))
        assert unmet(course=course, standing=a_standing(CSC101)) == (
            EligibilityReason.PREREQUISITE_NOT_PASSED,
        )

    def test_only_direct_prerequisites_are_checked(self) -> None:
        """The chain was walked when the student registered for the prerequisite itself."""
        assert unmet(standing=a_standing(CSC101)) == ()


class TestCreditLoad:
    def test_a_load_landing_exactly_on_the_cap_is_permitted(self) -> None:
        assert unmet(current_load=21) == ()

    def test_a_load_passing_the_cap_by_one_unit_is_refused(self) -> None:
        assert unmet(current_load=22) == (EligibilityReason.CREDIT_LOAD_EXCEEDED,)

    def test_the_refusal_says_what_the_load_would_have_become(self) -> None:
        failures = EligibilityRule().unmet(
            course=COURSE_WITH_PREREQUISITE,
            offering=an_offering(),
            standing=a_standing(CSC101),
            current_load=22,
            already_registered=False,
            is_financially_cleared=True,
        )
        assert "25 units" in failures[0].detail
        assert "24" in failures[0].detail

    def test_the_cap_is_the_policy_the_rule_was_built_with(self) -> None:
        assert unmet(current_load=13, rule=EligibilityRule(CreditLoadPolicy(max_units=15))) == (
            EligibilityReason.CREDIT_LOAD_EXCEEDED,
        )

    def test_a_student_on_probation_is_capped_no_differently_today(self) -> None:
        """Deliberate: whether probation lowers the cap is an unconfirmed institutional fact."""
        on_probation = a_standing(CSC101, standing=Standing.PROBATION)
        assert unmet(standing=on_probation, current_load=21) == ()


class TestCapacity:
    def test_refuses_a_course_whose_seats_are_gone(self) -> None:
        assert unmet(offering=an_offering(capacity=40, taken=40)) == (
            EligibilityReason.COURSE_AT_CAPACITY,
        )

    def test_permits_a_course_with_its_last_seat_free(self) -> None:
        assert unmet(offering=an_offering(capacity=40, taken=39)) == ()

    def test_the_rule_reads_the_offering_and_never_claims_a_seat(self) -> None:
        """Claiming while judging would mean giving the seat back on the next failure."""
        offering = an_offering(capacity=40, taken=10)
        unmet(offering=offering, standing=a_standing())
        assert offering.seats_taken == 10


class TestFinancialClearance:
    def test_refuses_a_student_billing_has_not_cleared(self) -> None:
        assert unmet(is_financially_cleared=False) == (EligibilityReason.NOT_FINANCIALLY_CLEARED,)


class TestRepeatsAndCarryOvers:
    def test_refuses_a_course_already_passed(self) -> None:
        """The student holds the credit; a second pass is a second grade for one requirement."""
        assert unmet(standing=a_standing(CSC101, CSC201)) == (EligibilityReason.ALREADY_PASSED,)

    def test_refuses_a_course_already_registered_this_term(self) -> None:
        assert unmet(already_registered=True) == (EligibilityReason.ALREADY_REGISTERED,)

    def test_permits_a_course_previously_failed(self) -> None:
        """A carry-over is re-registration for a course attempted and not passed."""
        assert unmet(standing=a_standing(CSC101)) == ()


class TestRetiredCourses:
    def test_refuses_a_course_the_catalog_has_retired(self) -> None:
        retired = CourseFacts(
            course_id=CSC201, credit_units=3, prerequisite_ids=(CSC101,), is_active=False
        )
        assert unmet(course=retired) == (EligibilityReason.COURSE_NOT_ACTIVE,)


class TestReportingEveryReason:
    def test_all_the_failures_come_back_at_once(self) -> None:
        """Not the first one found: a student turned away twice was told half the truth once."""
        reasons = unmet(
            offering=an_offering(capacity=1, taken=1),
            standing=a_standing(),
            current_load=24,
            is_financially_cleared=False,
        )
        assert set(reasons) == {
            EligibilityReason.PREREQUISITE_NOT_PASSED,
            EligibilityReason.CREDIT_LOAD_EXCEEDED,
            EligibilityReason.COURSE_AT_CAPACITY,
            EligibilityReason.NOT_FINANCIALLY_CLEARED,
        }

    @pytest.mark.parametrize("reason", list(EligibilityReason))
    def test_every_reason_carries_readable_detail(self, reason: EligibilityReason) -> None:
        """A screen shows the detail; an empty one would tell a student nothing."""
        assert reason.value


class TestTheRuleIsStateless:
    def test_one_instance_answers_about_different_students_independently(self) -> None:
        rule = EligibilityRule()
        assert unmet(standing=a_standing(), rule=rule) == (
            EligibilityReason.PREREQUISITE_NOT_PASSED,
        )
        assert unmet(standing=a_standing(CSC101), rule=rule) == ()
