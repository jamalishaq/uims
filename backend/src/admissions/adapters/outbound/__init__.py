"""Admissions outbound adapters.

In-memory implementations of the ports, good enough to run the whole context and its test
suite without a database. Phase 6 adds Postgres adapters alongside these; nothing above
this package should have to change when it does.
"""

from admissions.adapters.outbound.in_memory_applicant_repository import InMemoryApplicantRepository
from admissions.adapters.outbound.in_memory_entry_requirement_repository import (
    InMemoryProgramEntryRequirementRepository,
)

__all__ = [
    "InMemoryApplicantRepository",
    "InMemoryProgramEntryRequirementRepository",
]
