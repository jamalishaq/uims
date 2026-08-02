"""In-memory outbound adapters — the MVP's persistence and event publication.

Deliberately first: implementing the ports against a dict proves the port abstractions
before any SQL exists, so the Postgres adapters of Phase 6 are a swap at the composition
root and nothing above these classes changes.
"""

from faculty_department.adapters.outbound.in_memory_department_repository import (
    InMemoryDepartmentRepository,
)
from faculty_department.adapters.outbound.in_memory_event_publisher import InMemoryEventPublisher
from faculty_department.adapters.outbound.in_memory_faculty_repository import (
    InMemoryFacultyRepository,
)
from faculty_department.adapters.outbound.in_memory_lecturer_repository import (
    InMemoryLecturerRepository,
)
from faculty_department.adapters.outbound.in_memory_program_repository import (
    InMemoryProgramRepository,
)
from faculty_department.adapters.outbound.in_memory_session_repository import (
    InMemorySessionRepository,
)

__all__ = [
    "InMemoryDepartmentRepository",
    "InMemoryEventPublisher",
    "InMemoryFacultyRepository",
    "InMemoryLecturerRepository",
    "InMemoryProgramRepository",
    "InMemorySessionRepository",
]
