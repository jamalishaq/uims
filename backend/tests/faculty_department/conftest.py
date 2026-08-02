"""Wiring for the Faculty & Department tests.

This module is the swap point. Phase 6 replaces the in-memory adapters with Postgres
ones, and the requirement is that the application test suite runs unchanged against
both — so adapter construction happens *only* here, and every fixture is annotated with
its port type rather than the concrete class. A test that names an adapter directly is a
test that would have to be rewritten later.
"""

import pytest

from faculty_department.adapters.outbound import (
    InMemoryDepartmentRepository,
    InMemoryEventPublisher,
    InMemoryFacultyRepository,
    InMemoryLecturerRepository,
    InMemoryProgramRepository,
    InMemorySessionRepository,
)
from faculty_department.application import SubmitGrade
from faculty_department.ports import (
    DepartmentRepositoryPort,
    EventPublisherPort,
    FacultyRepositoryPort,
    LecturerRepositoryPort,
    ProgramRepositoryPort,
    SessionRepositoryPort,
)


@pytest.fixture
def faculties() -> FacultyRepositoryPort:
    return InMemoryFacultyRepository()


@pytest.fixture
def departments() -> DepartmentRepositoryPort:
    return InMemoryDepartmentRepository()


@pytest.fixture
def programs() -> ProgramRepositoryPort:
    return InMemoryProgramRepository()


@pytest.fixture
def lecturers() -> LecturerRepositoryPort:
    return InMemoryLecturerRepository()


@pytest.fixture
def sessions() -> SessionRepositoryPort:
    return InMemorySessionRepository()


@pytest.fixture
def events() -> InMemoryEventPublisher:
    """Concrete on purpose: this one is the spy the tests read ``published`` from."""
    return InMemoryEventPublisher()


@pytest.fixture
def submit_grade(
    lecturers: LecturerRepositoryPort,
    sessions: SessionRepositoryPort,
    events: EventPublisherPort,
) -> SubmitGrade:
    return SubmitGrade(lecturers=lecturers, sessions=sessions, events=events)
