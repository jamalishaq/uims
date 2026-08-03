"""Admissions outbound adapters.

In-memory implementations of the ports, good enough to run the whole context and its test
suite without a database. Phase 6 adds Postgres adapters alongside these; nothing above
this package should have to change when it does.

``InMemoryProgramInfoAdapter`` is the odd one out and the important one: it is not
persistence but an anti-corruption layer, standing where Faculty & Department will be
reached over a boundary that is not a Python import. It is fed its answers rather than
reading that context, which is the dependency rule showing up as a constructor.
"""

from admissions.adapters.outbound.faculty_department_program_info_adapter import (
    FacultyDepartmentProgramInfoAdapter,
    ProgramPlacement,
    ProgramPlacementSource,
)
from admissions.adapters.outbound.in_memory_admission_cycle_repository import (
    InMemoryAdmissionCycleRepository,
)
from admissions.adapters.outbound.in_memory_alternative_program_policy_repository import (
    InMemoryAlternativeProgramPolicyRepository,
)
from admissions.adapters.outbound.in_memory_applicant_repository import InMemoryApplicantRepository
from admissions.adapters.outbound.in_memory_entry_requirement_repository import (
    InMemoryProgramEntryRequirementRepository,
)
from admissions.adapters.outbound.in_memory_program_info_adapter import InMemoryProgramInfoAdapter

__all__ = [
    "FacultyDepartmentProgramInfoAdapter",
    "InMemoryAdmissionCycleRepository",
    "InMemoryAlternativeProgramPolicyRepository",
    "InMemoryApplicantRepository",
    "InMemoryProgramEntryRequirementRepository",
    "InMemoryProgramInfoAdapter",
    "ProgramPlacement",
    "ProgramPlacementSource",
]
