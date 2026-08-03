"""Pydantic request and response models. They go no further than this package.

Nothing inward takes one and nothing inward returns one: a use case is handed a ``*Command``
built from primitives, and answers with a ``CourseView``. That is the "DTOs at the application
boundary" half of Phase 6.2, and it is what lets the whole HTTP layer be replaced — by a CLI, a
message consumer, a second API version — without a use case noticing.

Request models validate *shape*, never rules. ``credit_units`` is constrained to be a positive
integer because a negative one is not a number of credits at all and rejecting it costs a round
trip; whether 7 is a sensible number of credits is the domain's judgement, and
``require_credit_units`` makes it. A validator here that duplicated a domain rule would be a
rule with two homes and one of them silently out of date.
"""

from pydantic import BaseModel, ConfigDict, Field

from course_catalog.application.views import CourseView


class RegisterCourseRequest(BaseModel):
    """A new course."""

    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(min_length=1)
    department_id: str = Field(min_length=1)
    code: str = Field(min_length=1, description="Upper-cased by the domain, e.g. 'CSC101'.")
    title: str = Field(min_length=1)
    credit_units: int = Field(gt=0)


class AmendCourseRequest(BaseModel):
    """Whichever fields of a course are being changed.

    Every field is optional and ``None`` means "leave it alone" — the shape ``AmendCourseCommand``
    already takes. That does mean a title cannot be cleared through this route, which is correct:
    a course with no title is not a state the domain permits.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1)
    credit_units: int | None = Field(default=None, gt=0)
    department_id: str | None = Field(default=None, min_length=1)


class CourseResponse(BaseModel):
    """One course, as the catalog holds it."""

    course_id: str
    department_id: str
    code: str
    title: str
    credit_units: int
    is_active: bool
    prerequisite_ids: tuple[str, ...]

    @classmethod
    def of(cls, view: CourseView) -> "CourseResponse":
        return cls(**vars(view))


class CourseListResponse(BaseModel):
    """A department's courses.

    Wrapped in an object rather than returned as a bare array: a top-level JSON array is the
    shape that cannot be extended, and the day this needs a total or a cursor there is nowhere
    to put it without breaking every client.
    """

    courses: tuple[CourseResponse, ...]


class PrerequisiteChainResponse(BaseModel):
    """Every course that must be passed before one course, transitively."""

    course_id: str
    prerequisite_ids: tuple[str, ...]
