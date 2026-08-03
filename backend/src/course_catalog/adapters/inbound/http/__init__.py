"""Course Catalog's HTTP adapter.

One router, its Pydantic models, and the table saying which status each refusal leaves as.
Nothing here imports a domain type except the exceptions it maps — see rule (d) in
``tests/architecture/test_dependency_rule.py`` and the carve-out it names.
"""

from course_catalog.adapters.inbound.http.errors import EXCEPTION_STATUSES
from course_catalog.adapters.inbound.http.router import (
    STATE_KEY,
    CourseCatalogDependencies,
    router,
)

__all__ = [
    "EXCEPTION_STATUSES",
    "STATE_KEY",
    "CourseCatalogDependencies",
    "router",
]
