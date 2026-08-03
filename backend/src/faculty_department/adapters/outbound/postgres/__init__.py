"""Postgres outbound adapters — the persistence the in-memory ones stood in for.

Phase 6.1. The in-memory adapters beside this package were written first on purpose, to prove
the port abstractions before any SQL existed; what that bought is that this package adds five
classes and changes nothing above them. The application layer, the use cases and the tests
that drive them do not know which of the two they are holding, and the composition root is
where they find out.
"""

from faculty_department.adapters.outbound.postgres._tables import SCHEMA, metadata
from faculty_department.adapters.outbound.postgres.repositories import (
    PostgresDepartmentRepository,
    PostgresFacultyRepository,
    PostgresLecturerRepository,
    PostgresProgramRepository,
    PostgresSessionRepository,
)

__all__ = [
    "SCHEMA",
    "PostgresDepartmentRepository",
    "PostgresFacultyRepository",
    "PostgresLecturerRepository",
    "PostgresProgramRepository",
    "PostgresSessionRepository",
    "metadata",
]
