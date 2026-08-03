"""Wiring for the Enrollment tests.

This module is the swap point. Phase 6 replaces the in-memory repositories with Postgres
ones and Phase 5.2 replaces the clearance stub with the real Billing adapter, and the
requirement in both cases is that the application test suite runs unchanged — so adapter
construction happens *only* here, and the repository fixtures are annotated with their port
types rather than the concrete class.

The three query adapters are annotated concretely, because a test has to tell them what the
other contexts would answer and ``register``/``deny`` are not on the ports. That is the
shape of an anti-corruption adapter rather than a leak: what replaces them is a client, and
a test that needed one would be an integration test living somewhere else.

The domain tests take nothing from this file. They build aggregates directly and assert on
them, because a domain test that needed a repository would be evidence that logic had
leaked out of the domain layer (CLAUDE.md section 2).
"""

import pytest

from enrollment.adapters.outbound import (
    InMemoryCourseInfoAdapter,
    InMemoryCourseOfferingRepository,
    InMemoryEnrollmentRepository,
    InMemoryStudentAcademicStandingAdapter,
    StubFinancialClearanceAdapter,
)
from enrollment.application import RegisterForCourse
from enrollment.ports import CourseOfferingRepositoryPort, EnrollmentRepositoryPort


@pytest.fixture
def enrollments() -> EnrollmentRepositoryPort:
    return InMemoryEnrollmentRepository()


@pytest.fixture
def offerings() -> CourseOfferingRepositoryPort:
    return InMemoryCourseOfferingRepository()


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
