"""Pydantic request and response models. They go no further than this package."""

from pydantic import BaseModel, ConfigDict, Field

from faculty_department.application.views import (
    DepartmentView,
    FacultyView,
    GradeSubmittedView,
    LecturerView,
    ProgramPlacementView,
    ProgramView,
    SessionView,
)


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


# ---- the academic structure, which had no write path until now ----


class CreateFacultyRequest(BaseModel):
    """A faculty, e.g. the Faculty of Science."""

    model_config = ConfigDict(extra="forbid")

    faculty_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    code: str = Field(min_length=1)


class FacultyResponse(BaseModel):
    """A faculty as this context holds it."""

    faculty_id: str
    name: str
    code: str

    @classmethod
    def of(cls, view: FacultyView) -> "FacultyResponse":
        return cls(**vars(view))


class CreateDepartmentRequest(BaseModel):
    """A department inside a faculty that already exists.

    ``code`` is the alphabetic code (``CSC``). The four numeric digits a matric number carries
    are Student Profile's translation of it and are configured there, so nothing here asks.
    """

    model_config = ConfigDict(extra="forbid")

    department_id: str = Field(min_length=1)
    faculty_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    code: str = Field(min_length=1)


class DepartmentResponse(BaseModel):
    """A department and the faculty it sits in."""

    department_id: str
    faculty_id: str
    name: str
    code: str

    @classmethod
    def of(cls, view: DepartmentView) -> "DepartmentResponse":
        return cls(**vars(view))


class CreateProgramRequest(BaseModel):
    """A program offered by a department that already exists.

    There is no ``is_admitting`` field: a program is created closed, and opening it is a
    separate decision on a program that exists rather than a side effect of describing one.
    """

    model_config = ConfigDict(extra="forbid")

    program_id: str = Field(min_length=1)
    department_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    code: str = Field(min_length=1)


class SetProgramAdmissionsRequest(BaseModel):
    """Open or close a program's admissions window."""

    model_config = ConfigDict(extra="forbid")

    is_admitting: bool


class ProgramResponse(BaseModel):
    """A program, its department, and whether it is taking applications."""

    program_id: str
    department_id: str
    name: str
    code: str
    is_admitting: bool

    @classmethod
    def of(cls, view: ProgramView) -> "ProgramResponse":
        return cls(**vars(view))


class ProgramListResponse(BaseModel):
    """Every program a department offers. An empty list is a normal answer."""

    programs: tuple[ProgramResponse, ...]


class PlannedSemesterSchema(BaseModel):
    """One semester of a planned session."""

    model_config = ConfigDict(extra="forbid")

    semester_id: str = Field(min_length=1)
    ordinal: int = Field(description="1 for the first semester, 2 for the second.")


class PlanSessionRequest(BaseModel):
    """An academic session, described before it starts.

    ``academic_year`` is the starting year — 2026 for the 2026/2027 session. The label is
    derived from it, so the two cannot disagree.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    academic_year: int
    semesters: tuple[PlannedSemesterSchema, ...]


class SemesterResponse(BaseModel):
    """One semester of a session. ``ordinal`` is 1 or 2, as the domain holds it."""

    semester_id: str
    ordinal: int


class SessionResponse(BaseModel):
    """An academic session, its semesters, and whether it has opened."""

    session_id: str
    academic_year: int
    label: str
    status: str
    is_open: bool
    semesters: tuple[SemesterResponse, ...]

    @classmethod
    def of(cls, view: SessionView) -> "SessionResponse":
        return cls(
            **(
                vars(view)
                | {
                    "semesters": tuple(
                        SemesterResponse(**vars(semester)) for semester in view.semesters
                    )
                }
            )
        )


class RegisterLecturerRequest(BaseModel):
    """A lecturer and the department they belong to. They teach nothing yet."""

    model_config = ConfigDict(extra="forbid")

    lecturer_id: str = Field(min_length=1)
    department_id: str = Field(min_length=1)
    full_name: str = Field(min_length=1)


class CourseAssignmentResponse(BaseModel):
    """One course a lecturer teaches, in one session."""

    course_id: str
    session_id: str


class QualificationSchema(BaseModel):
    """One degree a lecturer holds.

    ``degree`` is free text and not an enum. Degree names vary by institution and by era —
    ``M.Eng``, ``MBBS``, ``B.A. (Hons)`` — and an enum that rejected a real one would force
    whoever entered it to pick a wrong one.
    """

    model_config = ConfigDict(extra="forbid")

    degree: str = Field(min_length=1)
    discipline: str = Field(min_length=1)
    institution: str = Field(min_length=1)
    year: int = Field(description="The year awarded. Must be in the past.")


class AmendLecturerProfileRequest(BaseModel):
    """A lecturer's staff record, as it should now read.

    A replacement rather than a patch: omitted fields **clear**, because this is a form being
    saved. ``rank`` and ``employment_status`` are the wire values (``senior lecturer``,
    ``full-time``); an unrecognised one is a 422 rather than a silently dropped field, since a
    dropped rank reads identically to nobody having filled it in.
    """

    model_config = ConfigDict(extra="forbid")

    rank: str | None = None
    employment_status: str | None = None
    qualifications: tuple[QualificationSchema, ...] = ()


class AssignLecturerToCourseRequest(BaseModel):
    """Which session a lecturer teaches a course in.

    The course is in the path, so it is not repeated here — two places to say the same thing is
    two places for them to disagree.

    Scoped to a session on purpose: teaching CSC101 in 2026/2027 says nothing about 2027/2028,
    which is what stops somebody grading a course forever on the strength of having taught it
    once.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)


class LecturerResponse(BaseModel):
    """A lecturer, their staff record and what they teach.

    ``rank`` and ``employment_status`` are ``null`` when nobody has recorded them — a real
    state, and one a default would hide by reading identically to a checked value.
    """

    lecturer_id: str
    department_id: str
    full_name: str
    rank: str | None
    employment_status: str | None
    qualifications: tuple[QualificationSchema, ...]
    assignments: tuple[CourseAssignmentResponse, ...]

    @classmethod
    def of(cls, view: LecturerView) -> "LecturerResponse":
        return cls(
            **(
                vars(view)
                | {
                    "qualifications": tuple(
                        QualificationSchema(**vars(held)) for held in view.qualifications
                    ),
                    "assignments": tuple(
                        CourseAssignmentResponse(**vars(assignment))
                        for assignment in view.assignments
                    ),
                }
            )
        )


class LecturerListResponse(BaseModel):
    """Everyone teaching in a department. An empty list is a normal answer."""

    lecturers: tuple[LecturerResponse, ...]
