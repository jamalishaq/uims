"""Postgres outbound adapters for Academic Records.

One repository, because this context declares one. The ``CourseCreditPort`` beside it is a
query into Course Catalog rather than storage, and its in-memory stand-in goes on standing in.
"""

from academic_records.adapters.outbound.postgres._tables import SCHEMA, metadata
from academic_records.adapters.outbound.postgres.repositories import (
    PostgresAcademicRecordRepository,
)

__all__ = ["SCHEMA", "PostgresAcademicRecordRepository", "metadata"]
