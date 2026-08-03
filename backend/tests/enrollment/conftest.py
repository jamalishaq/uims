"""Wiring for the Enrollment tests.

This module is the swap point, and Phase 6.1 is the second half of what it was waiting for.
``enrollments`` and ``offerings`` now come from ``adapters``, which resolves to the in-memory
classes or the Postgres ones depending on ``UMS_TEST_BACKEND`` — see ``tests/conftest.py``.
Adapter construction still happens *only* here, and the repository fixtures are still
annotated with their port types rather than the concrete class.

The three query adapters are annotated concretely, because a test has to tell them what the
other contexts would answer and ``register``/``deny`` are not on the ports. That is the
shape of an anti-corruption adapter rather than a leak: what replaces them is a client, and
a test that needed one would be an integration test living somewhere else.

The domain tests take nothing from this file. They build aggregates directly and assert on
them, because a domain test that needed a repository would be evidence that logic had
leaked out of the domain layer (CLAUDE.md section 2).
"""

import pytest
from tests.conftest import Adapters

from enrollment.adapters.outbound import (
    InMemoryCourseInfoAdapter,
    InMemoryStudentAcademicStandingAdapter,
    StubFinancialClearanceAdapter,
)
from enrollment.application import RegisterForCourse
from enrollment.ports import CourseOfferingRepositoryPort, EnrollmentRepositoryPort


@pytest.fixture
def enrollments(adapters: Adapters) -> EnrollmentRepositoryPort:
    return adapters.enrollments()


@pytest.fixture
def offerings(adapters: Adapters) -> CourseOfferingRepositoryPort:
    return adapters.offerings()


@pytest.fixture
def courses() -> InMemoryCourseInfoAdapter:
    """Concrete on purpose: tests call ``register``, which is the adapter's, not the port's."""
    return InMemoryCourseInfoAdapter()


@pytest.fixture
def standings() -> InMemoryStudentAcademicStandingAdapter:
    """Concrete on purpose: tests say what Academic Records would answer."""
    return InMemoryStudentAcademicStandingAdapter()


@pytest.fixture
def clearance() -> StubFinancialClearanceAdapter:
    """Concrete on purpose, and temporary: Phase 5.2 replaces it with the real adapter."""
    return StubFinancialClearanceAdapter()


@pytest.fixture
def register_for_course(
    enrollments: EnrollmentRepositoryPort,
    offerings: CourseOfferingRepositoryPort,
    courses: InMemoryCourseInfoAdapter,
    standings: InMemoryStudentAcademicStandingAdapter,
    clearance: StubFinancialClearanceAdapter,
) -> RegisterForCourse:
    return RegisterForCourse(enrollments, offerings, courses, standings, clearance)
