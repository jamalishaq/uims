"""Enrollment outbound adapters.

In-memory implementations of the ports, good enough to run the whole context and its test
suite without a database. Phase 6 adds Postgres adapters alongside the two repositories;
nothing above this package should have to change when it does.

The others are not persistence. ``InMemoryCourseInfoAdapter``,
``InMemoryStudentAcademicStandingAdapter`` and ``BillingFinancialClearanceAdapter`` are
anti-corruption layers, standing where Course Catalog, Academic Records and Billing are
reached over a boundary that is not a Python import; all three are fed their answers rather
than reading those contexts, which is the dependency rule showing up as a constructor.

``BillingFinancialClearanceAdapter`` is the one that carries a rule rather than a
translation: the ≥70%/100% thresholds live in it and nowhere else, and Phase 5.2 added it
without a line changing above this package. ``StubFinancialClearanceAdapter`` stays beside
it as the fake the application tests drive — the same relationship the two Course Catalog
answers would have if the catalog were reachable today.
"""

from enrollment.adapters.outbound.academic_records_standing_adapter import (
    AcademicRecordsStandingAdapter,
    StudentRecord,
    StudentRecordSource,
)
from enrollment.adapters.outbound.billing_financial_clearance_adapter import (
    BILLING_CLEARANCE_THRESHOLDS,
    BillingFinancialClearanceAdapter,
    ClearanceThresholds,
    MalformedSessionFeeError,
    SessionFeeLedger,
    SessionFeePosition,
)
from enrollment.adapters.outbound.course_catalog_course_info_adapter import (
    CourseCatalogCourseInfoAdapter,
    CourseRecord,
    CourseSource,
)
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
    "BILLING_CLEARANCE_THRESHOLDS",
    "AcademicRecordsStandingAdapter",
    "BillingFinancialClearanceAdapter",
    "ClearanceThresholds",
    "CourseCatalogCourseInfoAdapter",
    "CourseRecord",
    "CourseSource",
    "InMemoryCourseInfoAdapter",
    "InMemoryCourseOfferingRepository",
    "InMemoryEnrollmentRepository",
    "InMemoryStudentAcademicStandingAdapter",
    "MalformedSessionFeeError",
    "SessionFeeLedger",
    "SessionFeePosition",
    "StubFinancialClearanceAdapter",
    "StudentRecord",
    "StudentRecordSource",
]
