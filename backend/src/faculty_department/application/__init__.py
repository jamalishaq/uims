"""Faculty & Department use cases.

Thin by design: each one loads aggregates through ports, asks the domain to decide, and
publishes what happened. No business rule lives here.
"""

from faculty_department.application.errors import (
    ApplicationError,
    LecturerNotFoundError,
    SessionNotFoundError,
)
from faculty_department.application.read_program_placement import ReadProgramPlacement
from faculty_department.application.submit_grade import SubmitGrade, SubmitGradeCommand
from faculty_department.application.views import GradeSubmittedView, ProgramPlacementView

__all__ = [
    "ApplicationError",
    "GradeSubmittedView",
    "LecturerNotFoundError",
    "ProgramPlacementView",
    "ReadProgramPlacement",
    "SessionNotFoundError",
    "SubmitGrade",
    "SubmitGradeCommand",
]
