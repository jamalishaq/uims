"""Student Profile use cases.

Thin by design: load through ports, ask the domain to decide, store what happened. No
business rule lives here — in particular, nothing in this package knows how a matric
number is spelled.

There is one use case, on purpose. Both ways a student can be created go through it.
"""

from student_profile.application.errors import ApplicationError, ProgramPlacementUnknownError
from student_profile.application.register_new_student import (
    DEFAULT_ENTRY_LEVEL,
    RegisterNewStudent,
    RegisterNewStudentCommand,
)
from student_profile.application.views import StudentView

__all__ = [
    "DEFAULT_ENTRY_LEVEL",
    "ApplicationError",
    "ProgramPlacementUnknownError",
    "RegisterNewStudent",
    "RegisterNewStudentCommand",
    "StudentView",
]
