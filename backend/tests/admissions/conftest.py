"""Wiring for the Admissions tests.

This module is the swap point. Phase 6 replaces the in-memory adapters with Postgres ones,
and the requirement is that the application test suite runs unchanged against both — so
adapter construction happens *only* here, and every fixture is annotated with its port type
rather than the concrete class. A test that named ``InMemoryApplicantRepository`` in its
own body would be a test that had to be edited when the storage changed, which is exactly
the coupling the ports exist to prevent.

The domain tests take nothing from this file. They build aggregates directly and assert on
them, because a domain test that needed a repository would be evidence that logic had
leaked out of the domain layer (CLAUDE.md section 2).
"""

import pytest

from admissions.adapters.outbound import (
    InMemoryApplicantRepository,
    InMemoryProgramEntryRequirementRepository,
)
from admissions.application import ScreenApplicant
from admissions.ports import ApplicantRepositoryPort, ProgramEntryRequirementRepositoryPort


@pytest.fixture
def applicants() -> ApplicantRepositoryPort:
    return InMemoryApplicantRepository()


@pytest.fixture
def requirements() -> ProgramEntryRequirementRepositoryPort:
    return InMemoryProgramEntryRequirementRepository()


@pytest.fixture
def screen_applicant(
    applicants: ApplicantRepositoryPort,
    requirements: ProgramEntryRequirementRepositoryPort,
) -> ScreenApplicant:
    return ScreenApplicant(applicants, requirements)
