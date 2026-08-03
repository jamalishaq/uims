"""Enrollment outbound adapters.

In-memory implementations of the ports, good enough to run the whole context and its test
suite without a database. Phase 6 adds Postgres adapters alongside the two repositories;
nothing above this package should have to change when it does.

The other three are not persistence. ``InMemoryCourseInfoAdapter`` and
``InMemoryStudentAcademicStandingAdapter`` are anti-corruption layers, standing where Course
Catalog and Academic Records will be reached over a boundary that is not a Python import;
both are fed their answers rather than reading those contexts, which is the dependency rule
showing up as a constructor. ``StubFinancialClearanceAdapter`` stands in for a Billing
context that does not exist yet, and is the one file here with an expiry date on it —
Phase 5.2 replaces it, and nothing above this package may change when it does.
"""

from enrollment.adapters.outbound.in_memory_course_info_adapter import InMemoryCourseInfoAdapter
from enrollment.adapters.outbound.in_memory_course_offering_repository import (
    InMemoryCourseOfferingRepository,
)
from enrollment.adapters.outbound.in_memory_enrollment_repository import (
    InMemoryEnrollmentRepository,
)
from enrollment.adapters.outbound.in_memory_student_academic_standing_adapter import (
    InMemoryStudentAcademicStandingAdapter,
)
from enrollment.adapters.outbound.stub_financial_clearance_adapter import (
    StubFinancialClearanceAdapter,
)

__all__ = [
    "InMemoryCourseInfoAdapter",
    "InMemoryCourseOfferingRepository",
    "InMemoryEnrollmentRepository",
    "InMemoryStudentAcademicStandingAdapter",
    "StubFinancialClearanceAdapter",
]
