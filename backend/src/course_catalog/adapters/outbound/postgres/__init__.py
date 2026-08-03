"""Postgres outbound adapters for the catalog.

One class, standing in for ``InMemoryCourseRepository`` behind the same port. Reference data
with no notion of a student, which is why this is the shortest of the seven.
"""

from course_catalog.adapters.outbound.postgres._tables import SCHEMA, metadata
from course_catalog.adapters.outbound.postgres.repositories import PostgresCourseRepository

__all__ = ["SCHEMA", "PostgresCourseRepository", "metadata"]
