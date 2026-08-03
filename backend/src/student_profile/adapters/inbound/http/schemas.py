"""Pydantic request and response models. They go no further than this package.

Nothing here lets a caller supply a matric number. It is issued — by ``MatricNumberIssuer``,
against a per-department/year sequence — and a request that could name one would be a request
that could collide with a number a living student already holds.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from student_profile.application.register_new_student import DEFAULT_ENTRY_LEVEL
from student_profile.application.views import StudentView


class RegisterNewStudentRequest(BaseModel):
    """A student to create by hand, outside the matriculation path.

    ``applicant_id`` is optional because this is the *manual* path: a registrar creating a
    student who never went through Admissions has no applicant to point at. When it is
    supplied it links the two, which is what the event-driven path always does.
    """

    model_config = ConfigDict(extra="forbid")

    student_id: str = Field(min_length=1)
    program_id: str = Field(min_length=1)
    entry_session_id: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    date_of_birth: date | None = None
    email: str | None = None
    phone_number: str | None = None
    entry_level: int = Field(default=DEFAULT_ENTRY_LEVEL, gt=0)
    applicant_id: str | None = None


class StudentResponse(BaseModel):
    """One student, as Student Profile holds them."""

    student_id: str
    matric_number: str
    program_id: str
    entry_session_id: str
    entry_level: int
    applicant_id: str | None
    full_name: str
    date_of_birth: date | None
    email: str | None
    phone_number: str | None

    @classmethod
    def of(cls, view: StudentView) -> "StudentResponse":
        return cls(**vars(view))
