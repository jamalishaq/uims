"""Course Catalog outbound adapters.

In-memory implementations of the ports, good enough to run the whole context and its
test suite without a database. Phase 6 adds Postgres adapters alongside these; nothing
above this package should have to change when it does.
"""

from course_catalog.adapters.outbound.in_memory_course_repository import InMemoryCourseRepository

__all__ = [
    "InMemoryCourseRepository",
]
