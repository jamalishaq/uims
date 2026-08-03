"""Student Profile's HTTP adapter: the manual registration path, as Phase 2 said it would be."""

from student_profile.adapters.inbound.http.errors import EXCEPTION_STATUSES
from student_profile.adapters.inbound.http.router import (
    STATE_KEY,
    StudentProfileDependencies,
    router,
)

__all__ = [
    "EXCEPTION_STATUSES",
    "STATE_KEY",
    "StudentProfileDependencies",
    "router",
]
