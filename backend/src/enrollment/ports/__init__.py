"""Enrollment ports layer.

The interfaces the outside world plugs into: persistence for the ``Enrollment`` and
``CourseOffering`` aggregates, plus the three queries this context makes of others.
``CourseInfoPort`` asks Course Catalog what a course requires and is worth,
``StudentAcademicStandingPort`` asks Academic Records what a student has passed, and
``FinancialClearancePort`` asks Billing a single yes-or-no (CLAUDE.md section 3). All three
answer in types defined by *this* context — ``CourseFacts``, ``AcademicStanding``, a
``bool`` — and the translation from whatever those contexts actually hold happens in the
adapters.

Facts in, judgment here. Not one of these ports returns a decision: no adapter is asked
whether a student may register, only what is true about them. The deciding is
``EligibilityRule``'s, in the domain.

Not here, and deliberately: an event publisher. Enrollment announces nothing. Academic
Records builds its own model from ``GradeSubmitted`` and never queries this context, and
Billing's fees are flat per session with no Enrollment → Billing event (CLAUDE.md
section 3). There is also no schedule port and there must never be one — registration is
schedule-blind by permanent decision, and adding one would be an escalation rather than a
feature.
"""

from enrollment.ports.course_info import CourseInfoPort
from enrollment.ports.course_offering_repository import CourseOfferingRepositoryPort
from enrollment.ports.enrollment_repository import EnrollmentRepositoryPort
from enrollment.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
)
from enrollment.ports.financial_clearance import FinancialClearancePort
from enrollment.ports.student_academic_standing import StudentAcademicStandingPort

__all__ = [
    "AggregateNotFoundError",
    "CourseInfoPort",
    "CourseOfferingRepositoryPort",
    "DuplicateAggregateError",
    "EnrollmentRepositoryPort",
    "FinancialClearancePort",
    "PersistenceUnavailableError",
    "RepositoryError",
    "StudentAcademicStandingPort",
]
