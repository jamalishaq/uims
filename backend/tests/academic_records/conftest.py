"""Wiring for the Academic Records tests.

This module is the swap point. Phase 6 replaces the in-memory repository with a Postgres
one and the course-credit adapter with a client that speaks to Course Catalog, and the
requirement in both cases is that the application test suite runs unchanged — so adapter
construction happens *only* here, and the repository fixture is annotated with its port type
rather than the concrete class.

It is also this context's **composition root**, which is the more interesting half. The
``wired_bus`` fixture is the one place in the system where Faculty & Department's publisher
and Academic Records' handler are introduced to each other, and it is deliberately a *test*
module rather than production code: neither context may import the other (CLAUDE.md section
4), so somebody outside both has to do the introducing. In Phase 6 that somebody is the
application's startup; today it is this file, in the same way every other context is wired
by its own conftest.

Notice how little the wiring knows. It names an event by a string, hands the bus a callable,
and imports no event class from either side. That is what makes it a line of configuration
rather than a translation layer with opinions of its own.

The domain tests take nothing from this file. They build records and transcripts directly
and assert on them, because a domain test that needed a repository would be evidence that
logic had leaked out of the domain layer (CLAUDE.md section 2).
"""

import pytest

from academic_records.adapters.inbound import GRADE_SUBMITTED, GradeSubmittedHandler
from academic_records.adapters.outbound import (
    InMemoryAcademicRecordRepository,
    InMemoryCourseCreditAdapter,
)
from academic_records.application import CorrectGrade, ReadAcademicRecord, RecordSubmittedGrade
from academic_records.ports import AcademicRecordRepositoryPort
from faculty_department.adapters.outbound import InMemoryEventBus


@pytest.fixture
def records() -> AcademicRecordRepositoryPort:
    return InMemoryAcademicRecordRepository()


@pytest.fixture
def courses() -> InMemoryCourseCreditAdapter:
    """Concrete on purpose: tests call ``register``, which is the adapter's, not the port's."""
    return InMemoryCourseCreditAdapter()


@pytest.fixture
def record_submitted_grade(
    records: AcademicRecordRepositoryPort,
    courses: InMemoryCourseCreditAdapter,
) -> RecordSubmittedGrade:
    return RecordSubmittedGrade(records, courses)


@pytest.fixture
def correct_grade(records: AcademicRecordRepositoryPort) -> CorrectGrade:
    return CorrectGrade(records)


@pytest.fixture
def read_academic_record(records: AcademicRecordRepositoryPort) -> ReadAcademicRecord:
    return ReadAcademicRecord(records)


@pytest.fixture
def grade_submitted_handler(
    record_submitted_grade: RecordSubmittedGrade,
) -> GradeSubmittedHandler:
    return GradeSubmittedHandler(record_submitted_grade)


@pytest.fixture
def wired_bus(grade_submitted_handler: GradeSubmittedHandler) -> InMemoryEventBus:
    """A bus with Academic Records listening on it. The composition root, in two lines.

    Faculty & Department publishes into this; Academic Records comes out the other side.
    Nothing in ``src/`` knows both halves, and that this fixture does is what makes it
    wiring.
    """
    bus = InMemoryEventBus()
    bus.subscribe(GRADE_SUBMITTED, grade_submitted_handler.on_message)
    return bus
