"""Postgres outbound adapters for Admissions.

Four repositories, three of them keyed by ``(program_id, session_id)`` because the data is
session-scoped and last session's policy has to stay readable beside this one's. The fourth
holds the lifecycle that ``Applicant.restore`` exists to rebuild.
"""

from admissions.adapters.outbound.postgres._tables import SCHEMA, metadata
from admissions.adapters.outbound.postgres.repositories import (
    PostgresAdmissionCycleRepository,
    PostgresAlternativeProgramPolicyRepository,
    PostgresApplicantRepository,
    PostgresProgramEntryRequirementRepository,
)

__all__ = [
    "SCHEMA",
    "PostgresAdmissionCycleRepository",
    "PostgresAlternativeProgramPolicyRepository",
    "PostgresApplicantRepository",
    "PostgresProgramEntryRequirementRepository",
    "metadata",
]
