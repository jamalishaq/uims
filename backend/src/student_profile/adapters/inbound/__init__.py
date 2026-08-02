"""Student Profile inbound adapters — the ways the outside world reaches the use case.

One so far: the handler for Admissions' ``StudentMatriculated``. An HTTP adapter for the
manual registration path is a later phase and will call the same ``RegisterNewStudent``.
"""

from student_profile.adapters.inbound.student_matriculated_handler import (
    StudentMatriculatedHandler,
    StudentMatriculatedMessage,
)

__all__ = [
    "StudentMatriculatedHandler",
    "StudentMatriculatedMessage",
]
