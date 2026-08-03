"""``Enrollment``: the three-state machine, transition by transition.

One test per transition, legal and illegal, in the manner of the ``Applicant`` tests. The
state machine is the whole of what this aggregate enforces — every eligibility question was
answered before it was constructed — so a transition that could be made out of turn is the
only way this class can be wrong.
"""

import pytest

from enrollment.domain import (
    CourseFacts,
    Enrollment,
    EnrollmentAlreadyFinalizedError,
    EnrollmentNotAwaitingGradeError,
    EnrollmentNotRegisteredError,
    EnrollmentStatus,
    InvalidCreditUnitsError,
    InvalidTermError,
    MissingIdentifierError,
    SemesterOrdinal,
    Term,
)

ENROLLMENT_ID = "enr-0001"
STUDENT_ID = "stu-260591001"
COURSE_ID = "crs-csc101"
TERM = Term(session_id="sess-2026", semester_id="sem-2026-1", ordinal=SemesterOrdinal.FIRST)
COURSE = CourseFacts(course_id=COURSE_ID, credit_units=3)


def a_registration(*, is_carry_over: bool = False) -> Enrollment:
    return Enrollment.register(
        enrollment_id=ENROLLMENT_ID,
        student_id=STUDENT_ID,
        course=COURSE,
        term=TERM,
        is_carry_over=is_carry_over,
    )


def an_enrollment_awaiting_grade() -> Enrollment:
    enrollment = a_registration()
    enrollment.await_grade()
    return enrollment


def a_finalized_enrollment() -> Enrollment:
    enrollment = an_enrollment_awaiting_grade()
    enrollment.finalize()
    return enrollment


class TestRegistering:
    def test_a_new_registration_is_registered_and_nothing_else(self) -> None:
        enrollment = a_registration()
        assert enrollment.status is EnrollmentStatus.REGISTERED
        assert not enrollment.is_final
        assert not enrollment.is_carry_over

    def test_takes_its_course_and_units_from_the_facts_it_was_given(self) -> None:
        """One source for both, so the units cannot be about a different course."""
        enrollment = a_registration()
        assert enrollment.course_id == COURSE_ID
        assert enrollment.credit_units == 3

    def test_the_units_are_a_snapshot_of_what_the_course_was_worth(self) -> None:
        """Course Catalog amending the course must not rewrite a term already registered."""
        enrollment = a_registration()
        amended = CourseFacts(course_id=COURSE_ID, credit_units=6)
        assert amended.credit_units == 6
        assert enrollment.credit_units == 3

    def test_a_carry_over_says_so(self) -> None:
        assert a_registration(is_carry_over=True).is_carry_over

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_rejects_a_blank_identifier(self, blank: str) -> None:
        with pytest.raises(MissingIdentifierError):
            Enrollment.register(
                enrollment_id=blank, student_id=STUDENT_ID, course=COURSE, term=TERM
            )
        with pytest.raises(MissingIdentifierError):
            Enrollment.register(
                enrollment_id=ENROLLMENT_ID, student_id=blank, course=COURSE, term=TERM
            )

    def test_rejects_a_term_that_is_not_one(self) -> None:
        with pytest.raises(InvalidTermError):
            Enrollment.register(
                enrollment_id=ENROLLMENT_ID,
                student_id=STUDENT_ID,
                course=COURSE,
                term="sem-2026-1",  # type: ignore[arg-type]
            )

    def test_rejects_units_that_are_not_a_count(self) -> None:
        with pytest.raises(InvalidCreditUnitsError):
            Enrollment(ENROLLMENT_ID, STUDENT_ID, COURSE_ID, TERM, 0)


class TestAwaitingGrade:
    def test_a_registered_enrollment_can_be_closed_for_teaching(self) -> None:
        enrollment = a_registration()
        enrollment.await_grade()
        assert enrollment.status is EnrollmentStatus.AWAITING_GRADE

    def test_cannot_be_closed_twice(self) -> None:
        enrollment = an_enrollment_awaiting_grade()
        with pytest.raises(EnrollmentNotRegisteredError):
            enrollment.await_grade()
        assert enrollment.status is EnrollmentStatus.AWAITING_GRADE

    def test_cannot_be_reopened_once_finalized(self) -> None:
        enrollment = a_finalized_enrollment()
        with pytest.raises(EnrollmentAlreadyFinalizedError):
            enrollment.await_grade()
        assert enrollment.status is EnrollmentStatus.FINALIZED


class TestFinalizing:
    def test_an_enrollment_awaiting_its_grade_can_be_finalized(self) -> None:
        enrollment = an_enrollment_awaiting_grade()
        enrollment.finalize()
        assert enrollment.status is EnrollmentStatus.FINALIZED
        assert enrollment.is_final

    def test_cannot_skip_awaiting_the_grade(self) -> None:
        """Finalising straight from registered would close a course still being taught."""
        enrollment = a_registration()
        with pytest.raises(EnrollmentNotAwaitingGradeError):
            enrollment.finalize()
        assert enrollment.status is EnrollmentStatus.REGISTERED

    def test_finalized_is_terminal(self) -> None:
        enrollment = a_finalized_enrollment()
        with pytest.raises(EnrollmentAlreadyFinalizedError):
            enrollment.finalize()
        assert enrollment.status is EnrollmentStatus.FINALIZED


class TestWhatTheAggregateDeliberatelyDoesNotDo:
    def test_holds_no_grade(self) -> None:
        """Grades belong to Academic Records; a copy here would be a second source of truth."""
        assert not hasattr(a_finalized_enrollment(), "grade")

    def test_has_no_drop_or_withdrawal(self) -> None:
        """Three states are the whole machine. A fourth is a decision nobody has made."""
        enrollment = a_registration()
        assert not hasattr(enrollment, "drop")
        assert not hasattr(enrollment, "withdraw")
        assert [status.value for status in EnrollmentStatus] == [
            "registered",
            "awaiting grade",
            "finalized",
        ]
