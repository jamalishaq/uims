"""Faculty & Department's HTTP adapter.

Two routes. The context owns far more than two things; what it has *use cases* for is grade
submission and — as of this phase — the placement read the cross-context adapters are built on.
See ``router.py`` on why the rest has no routes.
"""

from faculty_department.adapters.inbound.http.errors import EXCEPTION_STATUSES
from faculty_department.adapters.inbound.http.router import (
    STATE_KEY,
    FacultyDepartmentDependencies,
    router,
)

__all__ = [
    "EXCEPTION_STATUSES",
    "STATE_KEY",
    "FacultyDepartmentDependencies",
    "router",
]
