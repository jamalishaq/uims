"""Pydantic request and response models. They go no further than this package.

The response is a **discriminated union**, and that is the whole design of this adapter. A
registration ends one of two ways and neither is an error, so both leave as a 200 carrying an
``outcome`` tag a client switches on. A refusal in a 4xx would say the request was wrong; it
was not — it was answered.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from enrollment.application.views import (
    EligibilityFailureView,
    RegistrationAcceptedView,
    RegistrationRefusedView,
    TermView,
)


class RegisterForCourseRequest(BaseModel):
    """One student's request to take one course.

    ``semester_ordinal`` has no default, for the reason ``RegisterForCourseCommand`` gives:
    Billing's clearance rule differs between the two halves of a session, so a caller that
    omitted it would be asking about the wrong half and getting a confident answer.

    Nothing here says how many units the course is worth or whether it is a carry-over. Both
    are looked up — a caller that could state either could state it wrongly.
    """

    model_config = ConfigDict(extra="forbid")

    enrollment_id: str = Field(min_length=1)
    student_id: str = Field(min_length=1)
    course_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    semester_id: str = Field(min_length=1)
    semester_ordinal: int = Field(ge=1, le=2, description="1 for first semester, 2 for second.")


class TermResponse(BaseModel):
    """One semester of one session."""

    session_id: str
    semester_id: str
    ordinal: int
    label: str

    @classmethod
    def of(cls, view: TermView) -> "TermResponse":
        return cls(**vars(view))


class EligibilityFailureResponse(BaseModel):
    """One thing standing between a student and a course."""

    reason: str = Field(
        description="Stable machine-readable reason, e.g. 'not financially cleared'."
    )
    detail: str = Field(description="Written for a student to read. Not a stable interface.")

    @classmethod
    def of(cls, view: EligibilityFailureView) -> "EligibilityFailureResponse":
        return cls(**vars(view))


class RegistrationAcceptedResponse(BaseModel):
    """The student is registered and a seat has been claimed for them."""

    outcome: Literal["accepted"] = "accepted"
    enrollment_id: str
    student_id: str
    course_id: str
    term: TermResponse
    credit_units: int
    is_carry_over: bool
    seats_remaining: int

    @classmethod
    def of(cls, view: RegistrationAcceptedView) -> "RegistrationAcceptedResponse":
        return cls(
            enrollment_id=view.enrollment_id,
            student_id=view.student_id,
            course_id=view.course_id,
            term=TermResponse.of(view.term),
            credit_units=view.credit_units,
            is_carry_over=view.is_carry_over,
            seats_remaining=view.seats_remaining,
        )


class RegistrationRefusedResponse(BaseModel):
    """The student may not take this course, and here is everything standing in the way.

    ``reasons`` is never empty and holds *all* of them. A student refused for a missing
    prerequisite, who sorts it out and is then refused for a full course, has queued twice for
    information the university had both times.
    """

    outcome: Literal["refused"] = "refused"
    student_id: str
    course_id: str
    term: TermResponse
    reasons: tuple[EligibilityFailureResponse, ...]

    @classmethod
    def of(cls, view: RegistrationRefusedView) -> "RegistrationRefusedResponse":
        return cls(
            student_id=view.student_id,
            course_id=view.course_id,
            term=TermResponse.of(view.term),
            reasons=tuple(EligibilityFailureResponse.of(reason) for reason in view.reasons),
        )


RegistrationResponse = RegistrationAcceptedResponse | RegistrationRefusedResponse
"""Both ways a registration attempt can end, tagged by ``outcome``."""
