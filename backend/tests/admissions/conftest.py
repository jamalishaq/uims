"""Wiring for the Admissions tests.

This module is the swap point, and Phase 6.1 is what it was waiting for. The four repositories
now come from ``adapters``, which resolves to the in-memory classes or the Postgres ones
depending on ``UMS_TEST_BACKEND`` — see ``tests/conftest.py``. Adapter construction still
happens *only* here, and every fixture is still annotated with its port type rather than the
concrete class. A test that named ``InMemoryApplicantRepository`` in its
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
from tests.conftest import Adapters

from admissions.adapters.outbound import InMemoryEventBus, InMemoryProgramInfoAdapter
from admissions.application import (
    AcceptOffer,
    DeclineOffer,
    MakeOfferToApplicant,
    MatriculateApplicant,
    RecordAcceptanceFeePaid,
    ScreenApplicant,
    SubmitApplication,
)
from admissions.ports import (
    AdmissionCycleRepositoryPort,
    AlternativeProgramPolicyRepositoryPort,
    ApplicantRepositoryPort,
    ProgramEntryRequirementRepositoryPort,
)


@pytest.fixture
def applicants(adapters: Adapters) -> ApplicantRepositoryPort:
    return adapters.applicants()


@pytest.fixture
def requirements(adapters: Adapters) -> ProgramEntryRequirementRepositoryPort:
    return adapters.requirements()


@pytest.fixture
def cycles(adapters: Adapters) -> AdmissionCycleRepositoryPort:
    return adapters.cycles()


@pytest.fixture
def policies(adapters: Adapters) -> AlternativeProgramPolicyRepositoryPort:
    return adapters.policies()


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


@pytest.fixture
def events() -> InMemoryEventBus:
    """Concrete on purpose, like ``programs``: tests read ``published`` and subscribe, and
    neither is on ``EventPublisherPort``. The use cases still receive it as the port."""
    return InMemoryEventBus()


@pytest.fixture
def accept_offer(applicants: ApplicantRepositoryPort, events: InMemoryEventBus) -> AcceptOffer:
    return AcceptOffer(applicants, events)


@pytest.fixture
def decline_offer(
    applicants: ApplicantRepositoryPort, cycles: AdmissionCycleRepositoryPort
) -> DeclineOffer:
    return DeclineOffer(applicants, cycles)


@pytest.fixture
def matriculate_applicant(
    applicants: ApplicantRepositoryPort, events: InMemoryEventBus
) -> MatriculateApplicant:
    return MatriculateApplicant(applicants, events)


@pytest.fixture
def record_acceptance_fee_paid(applicants: ApplicantRepositoryPort) -> RecordAcceptanceFeePaid:
    return RecordAcceptanceFeePaid(applicants)
