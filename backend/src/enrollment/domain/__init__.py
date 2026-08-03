"""Enrollment domain layer.

Owns the judgment. Three other contexts supply the facts a registration is decided on —
what a course requires and is worth, what a student has passed, whether they are cleared to
register — and ``EligibilityRule`` is the one place any of it is weighed (CLAUDE.md
section 3). Owns, too, the two things a registration is made of: the ``Enrollment``
aggregate and its ``Registered → Awaiting Grade → Finalized`` machine, and the
``CourseOffering`` whose seats it claims. Stdlib only: no persistence, no ports, no HTTP
reaches this package.

Neither refusal says no by raising. ``CapacityExhausted`` is an outcome (see
``outcomes.py``) and an ineligible registration is a tuple of ``EligibilityFailure``,
because a full course and a student short of a prerequisite are how registration ordinarily
ends for a good number of the people who attempt it.

What this package deliberately has no notion of: money, and time of day. Fees are flat per
session and Billing answers a yes/no through a port; the timetable does not exist yet and
registration is schedule-blind by permanent decision (CLAUDE.md section 3, *Deferred:
Timetabling*).
"""

from enrollment.domain.course_offering import CourseOffering
from enrollment.domain.eligibility import (
    EligibilityFailure,
    EligibilityReason,
    EligibilityRule,
)
from enrollment.domain.enrollment import Enrollment, EnrollmentStatus
from enrollment.domain.errors import (
    EnrollmentAlreadyFinalizedError,
    EnrollmentError,
    EnrollmentNotAwaitingGradeError,
    EnrollmentNotRegisteredError,
    InvalidCapacityError,
    InvalidCreditLoadPolicyError,
    InvalidCreditUnitsError,
    InvalidSeatsTakenError,
    InvalidTermError,
    MissingIdentifierError,
)
from enrollment.domain.facts import AcademicStanding, CourseFacts, Standing
from enrollment.domain.outcomes import CapacityExhausted, SeatClaimed, SeatOutcome
from enrollment.domain.values import (
    MAX_CREDIT_UNITS_PER_SEMESTER,
    CreditLoadPolicy,
    SemesterOrdinal,
    Term,
)

__all__ = [
    "MAX_CREDIT_UNITS_PER_SEMESTER",
    "AcademicStanding",
    "CapacityExhausted",
    "CourseFacts",
    "CourseOffering",
    "CreditLoadPolicy",
    "EligibilityFailure",
    "EligibilityReason",
    "EligibilityRule",
    "Enrollment",
    "EnrollmentAlreadyFinalizedError",
    "EnrollmentError",
    "EnrollmentNotAwaitingGradeError",
    "EnrollmentNotRegisteredError",
    "EnrollmentStatus",
    "InvalidCapacityError",
    "InvalidCreditLoadPolicyError",
    "InvalidCreditUnitsError",
    "InvalidSeatsTakenError",
    "InvalidTermError",
    "MissingIdentifierError",
    "SeatClaimed",
    "SeatOutcome",
    "SemesterOrdinal",
    "Standing",
    "Term",
]
