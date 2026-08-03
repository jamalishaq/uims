"""Student Profile outbound adapters.

In-memory implementations of the ports, good enough to run the whole context and its test
suite without a database. Phase 6 adds Postgres adapters alongside these; nothing above
this package should have to change when it does.

``InMemoryDepartmentCodeAdapter`` is the odd one out: it is not persistence but the
anti-corruption layer in front of Faculty & Department, and it is the one file that knows
how that context's facts become ours.
"""

from student_profile.adapters.outbound.faculty_department_department_code_adapter import (
    FacultyDepartmentDepartmentCodeAdapter,
    ProgramPlacement,
    ProgramPlacementSource,
)
from student_profile.adapters.outbound.in_memory_department_code_adapter import (
    InMemoryDepartmentCodeAdapter,
)
from student_profile.adapters.outbound.in_memory_matric_sequence_repository import (
    InMemoryMatricSequenceRepository,
)
from student_profile.adapters.outbound.in_memory_student_repository import (
    InMemoryStudentRepository,
)

__all__ = [
    "FacultyDepartmentDepartmentCodeAdapter",
    "InMemoryDepartmentCodeAdapter",
    "InMemoryMatricSequenceRepository",
    "InMemoryStudentRepository",
    "ProgramPlacement",
    "ProgramPlacementSource",
]
