"""Wiring for the Faculty & Department tests.

This module is the swap point, and Phase 6.1 is what it was waiting for. The repositories
now come from ``adapters``, which resolves to the in-memory classes or the Postgres ones
depending on ``UMS_TEST_BACKEND`` — see ``tests/conftest.py``. Nothing else moved: the
fixture names, the port annotations and the tests that drive them are what they were, which
is the whole claim this phase makes.

Adapter construction still happens *only* here, and every fixture is still annotated with its
port type rather than the concrete class. A test that names an adapter directly is a test
that would have to be rewritten later — and now that "later" has arrived, the ones that did
not are the evidence.
"""

import pytest
from tests.conftest import Adapters

from faculty_department.adapters.outbound import InMemoryEventPublisher
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
def faculties(adapters: Adapters) -> FacultyRepositoryPort:
    return adapters.faculties()


@pytest.fixture
def departments(adapters: Adapters) -> DepartmentRepositoryPort:
    return adapters.departments()


@pytest.fixture
def programs(adapters: Adapters) -> ProgramRepositoryPort:
    return adapters.programs()


@pytest.fixture
def lecturers(adapters: Adapters) -> LecturerRepositoryPort:
    return adapters.lecturers()


@pytest.fixture
def sessions(adapters: Adapters) -> SessionRepositoryPort:
    return adapters.sessions()


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
