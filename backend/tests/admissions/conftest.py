"""Wiring for the Admissions tests.

This module is the swap point. Phase 6 replaces the in-memory adapters with Postgres ones,
and the requirement is that the application test suite runs unchanged against both — so
adapter construction happens *only* here, and every fixture is annotated with its port type
rather than the concrete class. A test that named ``InMemoryApplicantRepository`` in its
own body would be a test that had to be edited when the storage changed, which is exactly
the coupling the ports exist to prevent.

``programs`` is the one exception and is annotated concretely, because a test has to tell
it what Faculty & Department would answer and ``register`` is not on the port. That is the
shape of an anti-corruption adapter rather than a leak: what replaces it in Phase 6 is a
client, and a test that needed one would be an integration test living somewhere else.

The domain tests take nothing from this file. They build aggregates directly and assert on
them, because a domain test that needed a repository would be evidence that logic had
leaked out of the domain layer (CLAUDE.md section 2).
"""

import pytest

from admissions.adapters.outbound import (
    InMemoryAdmissionCycleRepository,
    InMemoryAlternativeProgramPolicyRepository,
    InMemoryApplicantRepository,
    InMemoryProgramEntryRequirementRepository,
    InMemoryProgramInfoAdapter,
)
from admissions.application import MakeOfferToApplicant, ScreenApplicant, SubmitApplication
from admissions.ports import (
    AdmissionCycleRepositoryPort,
    AlternativeProgramPolicyRepositoryPort,
    ApplicantRepositoryPort,
    ProgramEntryRequirementRepositoryPort,
)


@pytest.fixture
def applicants() -> ApplicantRepositoryPort:
    return InMemoryApplicantRepository()


@pytest.fixture
def requirements() -> ProgramEntryRequirementRepositoryPort:
    return InMemoryProgramEntryRequirementRepository()


@pytest.fixture
def cycles() -> AdmissionCycleRepositoryPort:
    return InMemoryAdmissionCycleRepository()


@pytest.fixture
def policies() -> AlternativeProgramPolicyRepositoryPort:
    return InMemoryAlternativeProgramPolicyRepository()


@pytest.fixture
def programs() -> InMemoryProgramInfoAdapter:
    """Concrete on purpose: tests call ``register``, which is the adapter's, not the port's."""
    return InMemoryProgramInfoAdapter()


@pytest.fixture
def screen_applicant(
    applicants: ApplicantRepositoryPort,
    requirements: ProgramEntryRequirementRepositoryPort,
) -> ScreenApplicant:
    return ScreenApplicant(applicants, requirements)


@pytest.fixture
def submit_application(
    applicants: ApplicantRepositoryPort,
    programs: InMemoryProgramInfoAdapter,
) -> SubmitApplication:
    return SubmitApplication(applicants, programs)


@pytest.fixture
def make_offer_to_applicant(
    applicants: ApplicantRepositoryPort,
    cycles: AdmissionCycleRepositoryPort,
    requirements: ProgramEntryRequirementRepositoryPort,
    policies: AlternativeProgramPolicyRepositoryPort,
) -> MakeOfferToApplicant:
    return MakeOfferToApplicant(applicants, cycles, requirements, policies)
