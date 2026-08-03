"""Admissions' HTTP adapter.

Three routes, their Pydantic models, and the table saying which status each refusal leaves as.
Screening failures and exhausted quotas are not in that table: they are outcomes.
"""

from admissions.adapters.inbound.http.errors import EXCEPTION_STATUSES
from admissions.adapters.inbound.http.router import STATE_KEY, AdmissionsDependencies, router

__all__ = [
    "EXCEPTION_STATUSES",
    "STATE_KEY",
    "AdmissionsDependencies",
    "router",
]
