"""Postgres outbound adapters for Student Profile.

The student register, and the intake counters whose whole purpose is to never hand out the
same ordinal twice. The counter is where this context's Postgres adapter differs in *kind*
from its in-memory one rather than in detail — see
:class:`~student_profile.adapters.outbound.postgres.repositories.PostgresMatricSequenceRepository`.
"""

from student_profile.adapters.outbound.postgres._tables import SCHEMA, metadata
from student_profile.adapters.outbound.postgres.repositories import (
    PostgresMatricSequenceRepository,
    PostgresStudentRepository,
)

__all__ = [
    "SCHEMA",
    "PostgresMatricSequenceRepository",
    "PostgresStudentRepository",
    "metadata",
]
