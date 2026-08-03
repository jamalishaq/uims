"""Course Catalog ports layer.

The interfaces the outside world plugs into: persistence for the catalog, and the
failures that persistence is allowed to express. No query ports and no event publisher
— this context is a source of reference data, not a consumer of anyone else's, and it
announces nothing (CLAUDE.md section 3). Enrollment reads it through a ``CourseInfoPort``
that belongs to Enrollment.
"""

from course_catalog.ports.course_repository import CourseRepositoryPort
from course_catalog.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
)

__all__ = [
    "AggregateNotFoundError",
    "CourseRepositoryPort",
    "DuplicateAggregateError",
    "PersistenceUnavailableError",
    "RepositoryError",
]
