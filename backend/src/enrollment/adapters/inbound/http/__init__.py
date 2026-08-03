"""Enrollment's HTTP adapter.

One router, its Pydantic models, and the table saying which status each refusal leaves as.
A *refused* registration is not in that table: it is an outcome, not a refusal of the request.
"""

from enrollment.adapters.inbound.http.errors import EXCEPTION_STATUSES
from enrollment.adapters.inbound.http.router import STATE_KEY, EnrollmentDependencies, router

__all__ = [
    "EXCEPTION_STATUSES",
    "STATE_KEY",
    "EnrollmentDependencies",
    "router",
]
