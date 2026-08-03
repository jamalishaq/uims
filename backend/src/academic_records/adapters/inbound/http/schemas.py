"""Pydantic request and response models. They go no further than this package.

**Every decimal is a string.** CGPA, GPA, grade points and quality points all cross as the
two-decimal figure the domain quantized, not as JSON numbers. A CGPA rendered as a float is a
CGPA a client can print as ``1.4999999999999998``, and 1.50 is the exact boundary at which a
student is or is not on probation. The number shown must be the number the rule used.

There is no request model for *recording* a grade, because there is no route: recording is
driven by ``GradeSubmitted`` arriving from Faculty & Department. Correcting is the human act,
and it is the only write this adapter exposes.
"""

from pydantic import BaseModel, ConfigDict, Field

from academic_records.application.views import (
    AcademicRecordView,
    CourseGradeView,
    GradeCorrectedView,
    GradeCorrectionView,
)


class CorrectGradeRequest(BaseModel):
    """An administrative correction to a grade already recorded.

    ``reason`` and ``authorized_by`` are required by the domain and restated as required here,
    which is the one place this file duplicates a rule on purpose: they are the entire audit
    trail, and a client should be told they are missing before the request is made rather than
    after. CLAUDE.md section 3: corrections "are a human use case, never event-driven".
    """

    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(min_length=1)
    semester_id: str = Field(min_length=1)
    corrected_score: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1, description="Why the original mark was wrong.")
    authorized_by: str = Field(min_length=1, description="Who authorised the change.")


class CourseGradeResponse(BaseModel):
    """One transcript line."""

    course_id: str
    semester_id: str
    score: int
    credit_units: int
    letter: str
    grade_point: str
    is_pass: bool
    quality_points: str

    @classmethod
    def of(cls, view: CourseGradeView) -> "CourseGradeResponse":
        return cls(**vars(view))


class GradeCorrectionResponse(BaseModel):
    """One audit entry against a corrected grade."""

    course_id: str
    semester_id: str
    previous_score: int
    corrected_score: int
    reason: str
    authorized_by: str

    @classmethod
    def of(cls, view: GradeCorrectionView) -> "GradeCorrectionResponse":
        return cls(**vars(view))


class AcademicRecordResponse(BaseModel):
    """A whole record: every attempt ever recorded, and what it adds up to.

    ``grades`` holds every attempt at a course, not the best one. A course failed and later
    passed is two lines and two contributions to the CGPA — CLAUDE.md section 3's confirmed
    carry-over rule.
    """

    student_id: str
    cgpa: str
    standing: str
    total_units: int
    grades: tuple[CourseGradeResponse, ...]
    semester_gpas: dict[str, str]
    passed_course_ids: tuple[str, ...]
    corrections: tuple[GradeCorrectionResponse, ...]

    @classmethod
    def of(cls, view: AcademicRecordView) -> "AcademicRecordResponse":
        return cls(
            student_id=view.student_id,
            cgpa=view.cgpa,
            standing=view.standing,
            total_units=view.total_units,
            grades=tuple(map(CourseGradeResponse.of, view.grades)),
            semester_gpas=view.semester_gpas,
            passed_course_ids=view.passed_course_ids,
            corrections=tuple(map(GradeCorrectionResponse.of, view.corrections)),
        )


class GradeCorrectedResponse(BaseModel):
    """What the correction changed, and what the record says now."""

    student_id: str
    correction: GradeCorrectionResponse
    cgpa: str
    standing: str

    @classmethod
    def of(cls, view: GradeCorrectedView) -> "GradeCorrectedResponse":
        return cls(
            student_id=view.student_id,
            correction=GradeCorrectionResponse.of(view.correction),
            cgpa=view.cgpa,
            standing=view.standing,
        )
