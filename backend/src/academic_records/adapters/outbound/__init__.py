"""Academic Records outbound adapters.

In-memory implementations of the two ports, good enough to run the whole context and its
test suite without a database. Phase 6 adds a Postgres adapter alongside the repository;
nothing above this package should have to change when it does.

:class:`InMemoryCourseCreditAdapter` is not persistence. It is the anti-corruption layer
standing where Course Catalog will be reached over a boundary that is not a Python import,
and it is *fed* its answers rather than reading that context — which is the dependency rule
showing up as a constructor.
"""

from academic_records.adapters.outbound.in_memory_academic_record_repository import (
    InMemoryAcademicRecordRepository,
)
from academic_records.adapters.outbound.in_memory_course_credit_adapter import (
    InMemoryCourseCreditAdapter,
)

__all__ = [
    "InMemoryAcademicRecordRepository",
    "InMemoryCourseCreditAdapter",
]
