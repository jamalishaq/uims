"""Student Profile ports layer.

The interfaces this context needs the outside world to satisfy: persistence for the
``Student`` aggregate and for the matric sequences, and one query port into Faculty &
Department for the facts a matric number is composed from. No event publisher — this
context announces nothing (CLAUDE.md section 3), and in particular sends no callback to
Admissions, because a matric number is not needed at acceptance-letter time.

Everything here is stated in this context's own language. Adapters translate; ports do
not.
"""

from student_profile.ports.department_code import DepartmentCodePort, MatricFormatInputs
from student_profile.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    RepositoryError,
)
from student_profile.ports.matric_sequence_repository import MatricSequenceRepositoryPort
from student_profile.ports.student_repository import StudentRepositoryPort

__all__ = [
    "AggregateNotFoundError",
    "DepartmentCodePort",
    "DuplicateAggregateError",
    "MatricFormatInputs",
    "MatricSequenceRepositoryPort",
    "RepositoryError",
    "StudentRepositoryPort",
]
