"""Faculty & Department outbound ports.

The interfaces this context needs the outside world to satisfy: persistence for each
aggregate, and a way to announce what happened. Everything here is stated in this
context's own language — adapters translate, ports do not.
"""

from faculty_department.ports.department_repository import DepartmentRepositoryPort
from faculty_department.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    RepositoryError,
)
from faculty_department.ports.event_publisher import EventPublisherPort
from faculty_department.ports.faculty_repository import FacultyRepositoryPort
from faculty_department.ports.lecturer_repository import LecturerRepositoryPort
from faculty_department.ports.program_repository import ProgramRepositoryPort
from faculty_department.ports.session_repository import SessionRepositoryPort

__all__ = [
    "AggregateNotFoundError",
    "DepartmentRepositoryPort",
    "DuplicateAggregateError",
    "EventPublisherPort",
    "FacultyRepositoryPort",
    "LecturerRepositoryPort",
    "ProgramRepositoryPort",
    "RepositoryError",
    "SessionRepositoryPort",
]
