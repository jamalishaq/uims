"""Primitives-shaped projections of what this context's use cases return.

``RegisterForCourse`` already refuses to hand out an ``Enrollment`` or a ``CourseOffering`` —
its two outcomes are application-layer DTOs. What they still carry is a ``Term`` and a tuple of
``EligibilityFailure``, and those are the two things flattened here.

The reason to flatten rather than serialise in the transport is ``EligibilityReason``'s own
docstring: the reason is "typed rather than prose so a caller can branch on the reason — an
inbound adapter showing 'pay your fees' needs to tell financial clearance from a missing
prerequisite". A view that dropped the reason and kept only ``detail`` would take that away.
So the enum's *value* crosses, and it crosses as the stable string the domain already chose.
"""

from dataclasses import dataclass

from enrollment.application.register_for_course import (
    RegistrationAccepted,
    RegistrationRefused,
)
from enrollment.domain.values import Term


@dataclass(frozen=True)
class TermView:
    """One semester of one session, flat.

    ``ordinal`` is the integer the enum carries (1 or 2), not its name — it is the number a
    student and a registrar both say out loud.
    """

    session_id: str
    semester_id: str
    ordinal: int
    label: str


@dataclass(frozen=True)
class EligibilityFailureView:
    """One thing standing between a student and a course, with the reason still branchable."""

    reason: str
    detail: str


@dataclass(frozen=True)
class RegistrationAcceptedView:
    """The student is registered and a seat is theirs."""

    enrollment_id: str
    student_id: str
    course_id: str
    term: TermView
    credit_units: int
    is_carry_over: bool
    seats_remaining: int

    @classmethod
    def of(cls, accepted: RegistrationAccepted) -> "RegistrationAcceptedView":
        return cls(
            enrollment_id=accepted.enrollment_id,
            student_id=accepted.student_id,
            course_id=accepted.course_id,
            term=_term_view(accepted.term),
            credit_units=accepted.credit_units,
            is_carry_over=accepted.is_carry_over,
            seats_remaining=accepted.seats_remaining,
        )


@dataclass(frozen=True)
class RegistrationRefusedView:
    """The student may not take this course, and every reason why — never just the first."""

    student_id: str
    course_id: str
    term: TermView
    reasons: tuple[EligibilityFailureView, ...]

    @classmethod
    def of(cls, refused: RegistrationRefused) -> "RegistrationRefusedView":
        return cls(
            student_id=refused.student_id,
            course_id=refused.course_id,
            term=_term_view(refused.term),
            reasons=tuple(
                EligibilityFailureView(reason=failure.reason.value, detail=failure.detail)
                for failure in refused.reasons
            ),
        )


def _term_view(term: Term) -> TermView:
    """Project a term. ``label`` is the domain's own rendering, not a second one built here."""
    return TermView(
        session_id=term.session_id,
        semester_id=term.semester_id,
        ordinal=term.ordinal.value,
        label=str(term),
    )
