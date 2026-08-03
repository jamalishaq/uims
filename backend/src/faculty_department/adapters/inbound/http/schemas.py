"""Pydantic request and response models. They go no further than this package."""

from pydantic import BaseModel, ConfigDict, Field

from faculty_department.application.views import GradeSubmittedView, ProgramPlacementView


class SubmitGradeRequest(BaseModel):
    """A lecturer's submission of one student's mark on one course.

    ``score`` is the raw mark out of 100. No letter and no grade point: what a mark is worth is
    Academic Records' grading scale, and a submission that carried a letter would be this
    context forming an opinion about a scale it does not own.
    """

    model_config = ConfigDict(extra="forbid")

    lecturer_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    student_id: str = Field(min_length=1)
    course_id: str = Field(min_length=1)
    semester_id: str = Field(min_length=1)
    score: int = Field(ge=0, le=100)


class GradeSubmittedResponse(BaseModel):
    """What the submission recorded and announced."""

    student_id: str
    course_id: str
    semester_id: str
    grade: int

    @classmethod
    def of(cls, view: GradeSubmittedView) -> "GradeSubmittedResponse":
        return cls(**vars(view))


class ProgramPlacementResponse(BaseModel):
    """Where a program sits and whether it is taking anybody, for one session.

    This is the read the cross-context adapters are built on, exposed over HTTP because a
    client that can register a student is a client that wants to show them their department.
    ``department_code`` is this context's alphabetic code; the numeric one a matric number
    carries is Student Profile's translation of it and deliberately does not appear here.
    """

    program_id: str
    department_id: str
    department_code: str
    faculty_id: str
    name: str
    code: str
    is_admitting: bool
    session_id: str
    session_start_year: int
    session_label: str
    session_is_open: bool

    @classmethod
    def of(cls, view: ProgramPlacementView) -> "ProgramPlacementResponse":
        return cls(**vars(view))
