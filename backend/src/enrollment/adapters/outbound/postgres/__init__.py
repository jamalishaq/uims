"""Postgres outbound adapters for Enrollment.

The two aggregates that hold registrations and seats. The three query ports this context
declares — into Course Catalog, Academic Records and Billing — are not here: they are clients
rather than repositories, and their in-memory stand-ins go on standing in.
"""

from enrollment.adapters.outbound.postgres._tables import SCHEMA, metadata
from enrollment.adapters.outbound.postgres.repositories import (
    PostgresCourseOfferingRepository,
    PostgresEnrollmentRepository,
)

__all__ = [
    "SCHEMA",
    "PostgresCourseOfferingRepository",
    "PostgresEnrollmentRepository",
    "metadata",
]
