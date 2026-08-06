"""Faculty & Department application layer.

Orchestration only. Every use case here loads through a port, delegates each decision to the
domain, and persists — whether a lecturer may grade a course is ``GradeSubmission``'s rule,
whether a session may open is ``Session``'s, and neither is restated here.

Two things in this layer are worth finding quickly.

``OpenSession`` is **the only publisher of ``SessionOpened``** in the system. Billing charges
every active account the session's fee on that event, so opening a session bills a cohort;
the subscription had been wired for phases with nothing to trigger it.

The creation use cases each **check the level above them** — a department's faculty, a
program's and a lecturer's department — because a dangling reference here surfaces far away
and much later, as ``ReadProgramPlacement`` answering ``None`` and an applicant being told
their program does not exist. That check is also what gives ``FacultyRepositoryPort`` its
first caller.
"""

from faculty_department.application.create_structure import (
    CreateDepartment,
    CreateDepartmentCommand,
    CreateFaculty,
    CreateFacultyCommand,
    CreateProgram,
    CreateProgramCommand,
    SetProgramAdmissions,
    SetProgramAdmissionsCommand,
)
from faculty_department.application.errors import (
    ApplicationError,
    DepartmentNotFoundError,
    FacultyNotFoundError,
    InvalidRankError,
    LecturerNotFoundError,
    ProgramNotFoundError,
    SessionNotFoundError,
)
from faculty_department.application.list_department_programs import (
    ListDepartmentPrograms,
    ListDepartmentProgramsCommand,
)
from faculty_department.application.manage_calendar import (
    OpenSession,
    OpenSessionCommand,
    PlannedSemester,
    PlanSession,
    PlanSessionCommand,
)
from faculty_department.application.manage_lecturers import (
    AmendLecturerProfile,
    AmendLecturerProfileCommand,
    AssignLecturerToCourse,
    AssignLecturerToCourseCommand,
    QualificationInput,
    WithdrawLecturerFromCourse,
    WithdrawLecturerFromCourseCommand,
)
from faculty_department.application.read_lecturers import (
    ListDepartmentLecturers,
    ListDepartmentLecturersCommand,
    ReadLecturer,
)
from faculty_department.application.read_program_placement import ReadProgramPlacement
from faculty_department.application.register_lecturer import (
    RegisterLecturer,
    RegisterLecturerCommand,
)
from faculty_department.application.submit_grade import SubmitGrade, SubmitGradeCommand
from faculty_department.application.views import (
    CourseAssignmentView,
    DepartmentView,
    FacultyView,
    GradeSubmittedView,
    LecturerView,
    ProgramPlacementView,
    ProgramView,
    QualificationView,
    SemesterView,
    SessionView,
)

__all__ = [
    "AmendLecturerProfile",
    "AmendLecturerProfileCommand",
    "ApplicationError",
    "AssignLecturerToCourse",
    "AssignLecturerToCourseCommand",
    "CourseAssignmentView",
    "CreateDepartment",
    "CreateDepartmentCommand",
    "CreateFaculty",
    "CreateFacultyCommand",
    "CreateProgram",
    "CreateProgramCommand",
    "DepartmentNotFoundError",
    "DepartmentView",
    "FacultyNotFoundError",
    "FacultyView",
    "GradeSubmittedView",
    "InvalidRankError",
    "LecturerNotFoundError",
    "LecturerView",
    "ListDepartmentLecturers",
    "ListDepartmentLecturersCommand",
    "ListDepartmentPrograms",
    "ListDepartmentProgramsCommand",
    "OpenSession",
    "OpenSessionCommand",
    "PlanSession",
    "PlanSessionCommand",
    "PlannedSemester",
    "ProgramNotFoundError",
    "ProgramPlacementView",
    "ProgramView",
    "QualificationInput",
    "QualificationView",
    "ReadLecturer",
    "ReadProgramPlacement",
    "RegisterLecturer",
    "RegisterLecturerCommand",
    "SemesterView",
    "SessionNotFoundError",
    "SessionView",
    "SetProgramAdmissions",
    "SetProgramAdmissionsCommand",
    "SubmitGrade",
    "SubmitGradeCommand",
    "WithdrawLecturerFromCourse",
    "WithdrawLecturerFromCourseCommand",
]
