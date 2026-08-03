"""Academic Records ports layer.

A short list, and the shortness is the design. Persistence for the one aggregate, and a
single query — :class:`CourseCreditPort` asks Course Catalog what a course is worth,
because a CGPA is weighted by credit units and ``GradeSubmitted`` does not carry them. It
answers in this context's own :class:`~academic_records.domain.facts.CourseCredits`, with
the anti-corruption translation in the adapter.

**No port into Enrollment, and there must never be one** (CLAUDE.md section 3). Whether the
student was registered, what their credit load was, whether their registration was
finalised — none of it enters a grade record. Enrollment reads *from* this context through
its own ``StudentAcademicStandingPort``; that traffic is one-way, and a port here pointing
back would close a loop that both contexts' docstrings promise stays open.

**No event publisher.** This context is the end of the chain. It consumes ``GradeSubmitted``
through an inbound adapter and announces nothing: no other context is waiting on a CGPA,
and Enrollment pulls the standing it needs when it needs it rather than being told. If
something downstream ever does need to react to a grade being recorded — a transcript
service, a graduation audit — it arrives here as a publisher port, and the decision to add
one is worth making on purpose.
"""

from academic_records.ports.academic_record_repository import AcademicRecordRepositoryPort
from academic_records.ports.course_credit import CourseCreditPort
from academic_records.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
)

__all__ = [
    "AcademicRecordRepositoryPort",
    "AggregateNotFoundError",
    "CourseCreditPort",
    "DuplicateAggregateError",
    "PersistenceUnavailableError",
    "RepositoryError",
]
