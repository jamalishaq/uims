"""Academic Records' HTTP adapter: read a record, correct a grade.

No route records a grade. That path is the event bus, and keeping it there is what stops an
HTTP client writing a transcript line without a lecturer's assignment ever being checked.
"""

from academic_records.adapters.inbound.http.errors import EXCEPTION_STATUSES
from academic_records.adapters.inbound.http.router import (
    STATE_KEY,
    AcademicRecordsDependencies,
    router,
)

__all__ = [
    "EXCEPTION_STATUSES",
    "STATE_KEY",
    "AcademicRecordsDependencies",
    "router",
]
