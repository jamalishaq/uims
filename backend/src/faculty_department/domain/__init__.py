"""Faculty & Department domain layer.

Owns faculties, departments, programs, lecturer-course assignments, the academic
calendar, and the act of grade submission. Stdlib only: no persistence, no ports,
no HTTP reaches this package.
"""

from faculty_department.domain.department import Department
from faculty_department.domain.errors import (
    DuplicateCourseAssignmentError,
    FacultyDepartmentError,
    InvalidAcademicYearError,
    InvalidLecturerProfileError,
    InvalidQualificationError,
    InvalidScoreError,
    InvalidSemesterSetError,
    LecturerNotAssignedToCourseError,
    MissingIdentifierError,
    SemesterNotInSessionError,
    SessionAlreadyClosedError,
    SessionAlreadyOpenError,
    SessionNotOpenError,
)
from faculty_department.domain.events import DomainEvent, GradeSubmitted, SessionOpened
from faculty_department.domain.faculty import Faculty
from faculty_department.domain.grade_submission import GradeSubmission
from faculty_department.domain.lecturer import CourseAssignment, Lecturer
from faculty_department.domain.program import Program
from faculty_department.domain.session import Semester, SemesterOrdinal, Session, SessionStatus
from faculty_department.domain.values import (
    AcademicYear,
    EmploymentStatus,
    Qualification,
    Rank,
    Score,
)

__all__ = [
    "AcademicYear",
    "CourseAssignment",
    "Department",
    "DomainEvent",
    "DuplicateCourseAssignmentError",
    "EmploymentStatus",
    "Faculty",
    "FacultyDepartmentError",
    "GradeSubmission",
    "GradeSubmitted",
    "InvalidAcademicYearError",
    "InvalidLecturerProfileError",
    "InvalidQualificationError",
    "InvalidScoreError",
    "InvalidSemesterSetError",
    "Lecturer",
    "LecturerNotAssignedToCourseError",
    "MissingIdentifierError",
    "Program",
    "Qualification",
    "Rank",
    "Score",
    "Semester",
    "SemesterNotInSessionError",
    "SemesterOrdinal",
    "Session",
    "SessionAlreadyClosedError",
    "SessionAlreadyOpenError",
    "SessionNotOpenError",
    "SessionOpened",
    "SessionStatus",
]
