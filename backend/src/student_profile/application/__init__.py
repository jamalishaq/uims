"""Student Profile use cases.

Thin by design: load through ports, ask the domain to decide, store what happened. No
business rule lives here — in particular, nothing in this package knows how a matric
number is spelled.

``RegisterNewStudent`` is still the only way a student is *created*, and both paths into the
system go through it — the manual route and Admissions' ``StudentMatriculated`` — which is
what makes one issuer, one sequence and one format true rather than aspirational.

The other two are what was missing around it. ``ReadStudent`` answers by any of the three
identifiers a student is known by, and ``CorrectStudentBioData`` fixes a misspelled name
without touching the matric number, which encodes entry year and department and has nothing
to do with how somebody is spelled.
"""

from student_profile.application.correct_student_bio_data import (
    CorrectStudentBioData,
    CorrectStudentBioDataCommand,
)
from student_profile.application.errors import (
    ApplicationError,
    ProgramPlacementUnknownError,
    StudentNotFoundError,
)
from student_profile.application.read_student import ReadStudent
from student_profile.application.register_new_student import (
    DEFAULT_ENTRY_LEVEL,
    RegisterNewStudent,
    RegisterNewStudentCommand,
)
from student_profile.application.views import StudentView

__all__ = [
    "DEFAULT_ENTRY_LEVEL",
    "ApplicationError",
    "CorrectStudentBioData",
    "CorrectStudentBioDataCommand",
    "ProgramPlacementUnknownError",
    "ReadStudent",
    "RegisterNewStudent",
    "RegisterNewStudentCommand",
    "StudentNotFoundError",
    "StudentView",
]
