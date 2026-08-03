"""Registration end to end: facts pulled through three ports, judgment made in the domain.

The build playbook's verification for this phase leads: a registration refused for an unmet
prerequisite, one refused for going over the credit cap, one refused for want of financial
clearance, and one that goes through. The rest are the edges those four run past.

The assertions that look redundant carry weight. After a refusal, the offering must still
read the seat count it had — a seat claimed for a student who was never registered is a
seat lost to somebody real, and nothing downstream would ever notice. After an acceptance,
exactly one seat is gone, and the enrollment is stored: the two writes are separate
transactions (CLAUDE.md section 4) and both have to have happened.

A LASU-shaped cast. CSC201 is worth 3 units and requires CSC101; MTH101 and PHY101 are the
3-unit courses used to fill a term up to its cap.
"""

import pytest

from enrollment.adapters.outbound import (
    InMemoryCourseInfoAdapter,
    InMemoryStudentAcademicStandingAdapter,
    StubFinancialClearanceAdapter,
)
from enrollment.application import (
    CourseNotFoundError,
    CourseOfferingNotFoundError,
    RegisterForCourse,
    RegisterForCourseCommand,
    RegistrationAccepted,
    RegistrationRefused,
)
from enrollment.domain import (
    CourseOffering,
    EligibilityReason,
    Enrollment,
    EnrollmentStatus,
    SemesterOrdinal,
    Term,
)
from enrollment.ports import CourseOfferingRepositoryPort, EnrollmentRepositoryPort

STUDENT_ID = "stu-260591001"
CSC101 = "crs-csc101"
CSC201 = "crs-csc201"
MTH101 = "crs-mth101"
PHY101 = "crs-phy101"

SESSION_ID = "sess-2026"
FIRST = Term(session_id=SESSION_ID, semester_id="sem-2026-1", ordinal=SemesterOrdinal.FIRST)
SECOND = Term(session_id=SESSION_ID, semester_id="sem-2026-2", ordinal=SemesterOrdinal.SECOND)


def a_command(
    course_id: str = CSC201,
    *,
    enrollment_id: str = "enr-0001",
    student_id: str = STUDENT_ID,
    term: Term = FIRST,
) -> RegisterForCourseCommand:
    return RegisterForCourseCommand(
        enrollment_id=enrollment_id,
        student_id=student_id,
        course_id=course_id,
        session_id=term.session_id,
        semester_id=term.semester_id,
        semester_ordinal=term.ordinal,
    )


@pytest.fixture(autouse=True)
def catalog(courses: InMemoryCourseInfoAdapter) -> InMemoryCourseInfoAdapter:
    """What Course Catalog would answer: CSC201 requires CSC101, everything is 3 units."""
    courses.register(CSC101, credit_units=3)
    courses.register(CSC201, credit_units=3, prerequisite_ids=(CSC101,))
    courses.register(MTH101, credit_units=3)
    courses.register(PHY101, credit_units=3)
    return courses


@pytest.fixture(autouse=True)
def open_offerings(offerings: CourseOfferingRepositoryPort) -> CourseOfferingRepositoryPort:
    """Every course is being run this term, with room in it."""
    for course_id in (CSC101, CSC201, MTH101, PHY101):
        offerings.add(CourseOffering.open(course_id, FIRST, capacity=40))
    return offerings


@pytest.fixture(autouse=True)
def passed_the_prerequisite(
    standings: InMemoryStudentAcademicStandingAdapter,
) -> InMemoryStudentAcademicStandingAdapter:
    """What Academic Records would answer: the student has CSC101 behind them."""
    standings.register(STUDENT_ID, passed_course_ids=(CSC101,))
    return standings


def fill_the_term(
    register_for_course: RegisterForCourse, *course_ids: str, term: Term = FIRST
) -> None:
    """Register the student for several courses, to push their load up against the cap."""
    for index, course_id in enumerate(course_ids):
        outcome = register_for_course.execute(
            a_command(course_id, enrollment_id=f"enr-fill-{index}", term=term)
        )
        assert isinstance(outcome, RegistrationAccepted)


class TestAPermittedRegistration:
    def test_the_student_is_registered_and_a_seat_is_claimed(
        self,
        register_for_course: RegisterForCourse,
        enrollments: EnrollmentRepositoryPort,
        offerings: CourseOfferingRepositoryPort,
    ) -> None:
        outcome = register_for_course.execute(a_command())

        assert isinstance(outcome, RegistrationAccepted)
        assert (outcome.student_id, outcome.course_id, outcome.term) == (STUDENT_ID, CSC201, FIRST)
        assert outcome.credit_units == 3

        stored = enrollments.get("enr-0001")
        assert isinstance(stored, Enrollment)
        assert stored.status is EnrollmentStatus.REGISTERED

        offering = offerings.get(CSC201, FIRST)
        assert offering is not None
        assert offering.seats_taken == 1
        assert outcome.seats_remaining == 39

    def test_exactly_one_seat_goes_per_registration(
        self, register_for_course: RegisterForCourse, offerings: CourseOfferingRepositoryPort
    ) -> None:
        for index in range(3):
            register_for_course.execute(
                a_command(MTH101, enrollment_id=f"enr-{index}", student_id=f"stu-{index}")
            )
        offering = offerings.get(MTH101, FIRST)
        assert offering is not None
        assert offering.seats_taken == 3

    def test_a_fresher_with_no_academic_record_can_register(
        self, register_for_course: RegisterForCourse
    ) -> None:
        """No record means passed nothing, not refused: this is everyone's first semester."""
        outcome = register_for_course.execute(a_command(MTH101, student_id="stu-fresher"))
        assert isinstance(outcome, RegistrationAccepted)

    def test_registering_the_same_course_in_a_later_term_is_a_different_registration(
        self,
        register_for_course: RegisterForCourse,
        offerings: CourseOfferingRepositoryPort,
    ) -> None:
        offerings.add(CourseOffering.open(MTH101, SECOND, capacity=40))
        register_for_course.execute(a_command(MTH101, enrollment_id="enr-first"))
        outcome = register_for_course.execute(
            a_command(MTH101, enrollment_id="enr-second", term=SECOND)
        )
        assert isinstance(outcome, RegistrationAccepted)


class TestRefusedForAnUnmetPrerequisite:
    def test_a_student_who_has_not_passed_the_prerequisite_is_refused(
        self, register_for_course: RegisterForCourse
    ) -> None:
        outcome = register_for_course.execute(a_command(CSC201, student_id="stu-no-history"))
        assert isinstance(outcome, RegistrationRefused)
        assert outcome.has(EligibilityReason.PREREQUISITE_NOT_PASSED)
        assert CSC101 in outcome.reasons[0].detail

    def test_the_refusal_writes_nothing(
        self,
        register_for_course: RegisterForCourse,
        enrollments: EnrollmentRepositoryPort,
        offerings: CourseOfferingRepositoryPort,
    ) -> None:
        """No enrollment stored, and — the one that would go unnoticed — no seat claimed."""
        register_for_course.execute(a_command(CSC201, student_id="stu-no-history"))
        offering = offerings.get(CSC201, FIRST)
        assert offering is not None
        assert offering.seats_taken == 0
        assert enrollments.get("enr-0001") is None


class TestRefusedForGoingOverTheCreditCap:
    def test_the_registration_that_lands_exactly_on_the_cap_is_accepted(
        self,
        register_for_course: RegisterForCourse,
        courses: InMemoryCourseInfoAdapter,
        offerings: CourseOfferingRepositoryPort,
    ) -> None:
        """A 21-unit term with a 3-unit course on top: exactly 24, which is the cap."""
        courses.register("crs-load21", credit_units=21)
        offerings.add(CourseOffering.open("crs-load21", FIRST, capacity=40))
        register_for_course.execute(a_command("crs-load21", enrollment_id="enr-load"))

        assert isinstance(register_for_course.execute(a_command(CSC201)), RegistrationAccepted)

    def test_the_registration_that_passes_the_cap_is_refused(
        self,
        register_for_course: RegisterForCourse,
        courses: InMemoryCourseInfoAdapter,
        offerings: CourseOfferingRepositoryPort,
        enrollments: EnrollmentRepositoryPort,
    ) -> None:
        """A 24-unit term with a 3-unit course on top: 27, over a cap of 24."""
        courses.register("crs-big", credit_units=24)
        offerings.add(CourseOffering.open("crs-big", FIRST, capacity=40))
        register_for_course.execute(a_command("crs-big", enrollment_id="enr-big"))

        outcome = register_for_course.execute(a_command(CSC201))
        assert isinstance(outcome, RegistrationRefused)
        assert outcome.has(EligibilityReason.CREDIT_LOAD_EXCEEDED)

        offering = offerings.get(CSC201, FIRST)
        assert offering is not None
        assert offering.seats_taken == 0
        assert enrollments.get("enr-0001") is None

    def test_the_cap_is_measured_over_the_term_and_not_the_session(
        self,
        register_for_course: RegisterForCourse,
        courses: InMemoryCourseInfoAdapter,
        offerings: CourseOfferingRepositoryPort,
    ) -> None:
        """A full first semester says nothing about what may be taken in the second."""
        courses.register("crs-big", credit_units=24)
        offerings.add(CourseOffering.open("crs-big", FIRST, capacity=40))
        offerings.add(CourseOffering.open(CSC201, SECOND, capacity=40))
        register_for_course.execute(a_command("crs-big", enrollment_id="enr-big"))

        outcome = register_for_course.execute(a_command(CSC201, term=SECOND))
        assert isinstance(outcome, RegistrationAccepted)


class TestRefusedForWantOfFinancialClearance:
    def test_a_student_billing_has_not_cleared_is_refused(
        self,
        register_for_course: RegisterForCourse,
        clearance: StubFinancialClearanceAdapter,
        enrollments: EnrollmentRepositoryPort,
        offerings: CourseOfferingRepositoryPort,
    ) -> None:
        clearance.deny(STUDENT_ID, FIRST)

        outcome = register_for_course.execute(a_command())
        assert isinstance(outcome, RegistrationRefused)
        assert outcome.has(EligibilityReason.NOT_FINANCIALLY_CLEARED)

        offering = offerings.get(CSC201, FIRST)
        assert offering is not None
        assert offering.seats_taken == 0
        assert enrollments.get("enr-0001") is None

    def test_clearance_is_asked_per_term_not_per_session(
        self,
        register_for_course: RegisterForCourse,
        clearance: StubFinancialClearanceAdapter,
        offerings: CourseOfferingRepositoryPort,
    ) -> None:
        """Billing's rule differs between the two halves of a session; the port carries the term."""
        offerings.add(CourseOffering.open(CSC201, SECOND, capacity=40))
        clearance.deny(STUDENT_ID, SECOND)

        assert isinstance(register_for_course.execute(a_command(CSC201)), RegistrationAccepted)
        assert isinstance(
            register_for_course.execute(a_command(CSC201, enrollment_id="enr-2", term=SECOND)),
            RegistrationRefused,
        )

    def test_the_stub_clears_everyone_it_has_not_been_told_about(
        self, register_for_course: RegisterForCourse
    ) -> None:
        """The Phase 5 stand-in: cleared until Billing exists to say otherwise."""
        assert isinstance(
            register_for_course.execute(a_command(MTH101, student_id="stu-unknown")),
            RegistrationAccepted,
        )


class TestRefusedForCapacity:
    def test_the_student_who_takes_the_last_seat_gets_it_and_the_next_one_does_not(
        self,
        register_for_course: RegisterForCourse,
        courses: InMemoryCourseInfoAdapter,
        offerings: CourseOfferingRepositoryPort,
        enrollments: EnrollmentRepositoryPort,
    ) -> None:
        courses.register("crs-popular", credit_units=3)
        offerings.add(CourseOffering.open("crs-popular", FIRST, capacity=1))

        first = register_for_course.execute(
            a_command("crs-popular", enrollment_id="enr-lucky", student_id="stu-a")
        )
        second = register_for_course.execute(
            a_command("crs-popular", enrollment_id="enr-late", student_id="stu-b")
        )

        assert isinstance(first, RegistrationAccepted)
        assert first.seats_remaining == 0
        assert isinstance(second, RegistrationRefused)
        assert second.has(EligibilityReason.COURSE_AT_CAPACITY)
        assert enrollments.get("enr-late") is None

    def test_a_full_course_stays_exactly_as_full_as_it_was(
        self, register_for_course: RegisterForCourse, offerings: CourseOfferingRepositoryPort
    ) -> None:
        """The invariant, seen from the use case: refusals never increment a seat count."""
        offering = offerings.get(CSC201, FIRST)
        assert offering is not None
        for _ in range(40):
            offering.claim_seat()
        offerings.save(offering)

        outcome = register_for_course.execute(a_command(CSC201))
        assert isinstance(outcome, RegistrationRefused)
        assert offering.seats_taken == 40


class TestRepeatsAndCarryOvers:
    def test_the_same_course_cannot_be_registered_twice_in_one_term(
        self, register_for_course: RegisterForCourse, offerings: CourseOfferingRepositoryPort
    ) -> None:
        register_for_course.execute(a_command(CSC201))
        outcome = register_for_course.execute(a_command(CSC201, enrollment_id="enr-again"))

        assert isinstance(outcome, RegistrationRefused)
        assert outcome.has(EligibilityReason.ALREADY_REGISTERED)
        offering = offerings.get(CSC201, FIRST)
        assert offering is not None
        assert offering.seats_taken == 1

    def test_a_course_already_passed_cannot_be_taken_again(
        self, register_for_course: RegisterForCourse
    ) -> None:
        outcome = register_for_course.execute(a_command(CSC101, enrollment_id="enr-repeat"))
        assert isinstance(outcome, RegistrationRefused)
        assert outcome.has(EligibilityReason.ALREADY_PASSED)

    def test_a_course_previously_failed_comes_back_as_a_carry_over(
        self,
        register_for_course: RegisterForCourse,
        offerings: CourseOfferingRepositoryPort,
    ) -> None:
        """Registered before, not among the passes: the definition of a carry-over."""
        offerings.add(CourseOffering.open(CSC201, SECOND, capacity=40))
        first_attempt = register_for_course.execute(a_command(CSC201))
        assert isinstance(first_attempt, RegistrationAccepted)
        assert not first_attempt.is_carry_over

        retake = register_for_course.execute(
            a_command(CSC201, enrollment_id="enr-retake", term=SECOND)
        )
        assert isinstance(retake, RegistrationAccepted)
        assert retake.is_carry_over


class TestQuestionsThatCannotBeAnswered:
    def test_a_course_the_catalog_does_not_know_is_an_error(
        self, register_for_course: RegisterForCourse
    ) -> None:
        with pytest.raises(CourseNotFoundError):
            register_for_course.execute(a_command("crs-nonexistent"))

    def test_a_course_nobody_is_running_this_term_is_an_error(
        self, register_for_course: RegisterForCourse
    ) -> None:
        """Different from a full course, which is a decision with a number behind it."""
        with pytest.raises(CourseOfferingNotFoundError):
            register_for_course.execute(a_command(CSC201, term=SECOND))

    def test_a_retired_course_is_refused_rather_than_raised(
        self,
        register_for_course: RegisterForCourse,
        courses: InMemoryCourseInfoAdapter,
    ) -> None:
        """It is a real course; declining to register anybody for it is a decision."""
        courses.retire(MTH101)
        outcome = register_for_course.execute(a_command(MTH101))
        assert isinstance(outcome, RegistrationRefused)
        assert outcome.has(EligibilityReason.COURSE_NOT_ACTIVE)


class TestEveryReasonAtOnce:
    def test_a_student_who_is_wrong_in_several_ways_is_told_all_of_them(
        self,
        register_for_course: RegisterForCourse,
        clearance: StubFinancialClearanceAdapter,
    ) -> None:
        clearance.deny("stu-no-history", FIRST)
        outcome = register_for_course.execute(a_command(CSC201, student_id="stu-no-history"))

        assert isinstance(outcome, RegistrationRefused)
        assert outcome.has(EligibilityReason.PREREQUISITE_NOT_PASSED)
        assert outcome.has(EligibilityReason.NOT_FINANCIALLY_CLEARED)


class TestNoScheduleAwareness:
    def test_two_courses_are_registrable_without_anyone_asking_when_they_meet(
        self, register_for_course: RegisterForCourse
    ) -> None:
        """Model A is permanent: registration is by eligibility, the timetable comes after."""
        assert isinstance(
            register_for_course.execute(a_command(MTH101, enrollment_id="enr-a")),
            RegistrationAccepted,
        )
        assert isinstance(
            register_for_course.execute(a_command(PHY101, enrollment_id="enr-b")),
            RegistrationAccepted,
        )
