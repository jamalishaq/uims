"""Course Catalog domain layer.

Owns course codes, titles, credit units, prerequisite chains, and the offering
department. Slow-changing reference data with no notion of a specific student. Stdlib
only: no persistence, no ports, no HTTP reaches this package.
"""

from course_catalog.domain.course import Course
from course_catalog.domain.errors import (
    CourseCatalogError,
    DuplicatePrerequisiteError,
    InvalidCreditUnitsError,
    MissingIdentifierError,
    PrerequisiteCycleError,
    PrerequisiteNotRequiredError,
    SelfPrerequisiteError,
)
from course_catalog.domain.prerequisites import PrerequisiteGraph
from course_catalog.domain.values import MIN_CREDIT_UNITS

__all__ = [
    "MIN_CREDIT_UNITS",
    "Course",
    "CourseCatalogError",
    "DuplicatePrerequisiteError",
    "InvalidCreditUnitsError",
    "MissingIdentifierError",
    "PrerequisiteCycleError",
    "PrerequisiteGraph",
    "PrerequisiteNotRequiredError",
    "SelfPrerequisiteError",
]
