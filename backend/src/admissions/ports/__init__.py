"""Admissions ports layer.

The interfaces the outside world plugs into: persistence for the ``Applicant`` and
``AdmissionCycle`` aggregates and for this context's own session-scoped policy — entry
requirements and alternative-program chains — plus the one query this context makes of
another. ``ProgramInfoPort`` asks Faculty & Department whether a program exists and is
admitting, checked at application time (CLAUDE.md section 3), and answers in a type
defined here rather than there.

Not here yet, and deliberately: the event publisher this context announces
``OfferAccepted`` and ``StudentMatriculated`` through. Neither event is raised by anything
built so far — an offer being *made* is not among the two facts Admissions publishes, and
the acceptance and matriculation flows that do publish them come later.
"""

from admissions.ports.admission_cycle_repository import AdmissionCycleRepositoryPort
from admissions.ports.alternative_program_policy_repository import (
    AlternativeProgramPolicyRepositoryPort,
)
from admissions.ports.applicant_repository import ApplicantRepositoryPort
from admissions.ports.entry_requirement_repository import ProgramEntryRequirementRepositoryPort
from admissions.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
)
from admissions.ports.program_info import ProgramInfo, ProgramInfoPort

__all__ = [
    "AdmissionCycleRepositoryPort",
    "AggregateNotFoundError",
    "AlternativeProgramPolicyRepositoryPort",
    "ApplicantRepositoryPort",
    "DuplicateAggregateError",
    "PersistenceUnavailableError",
    "ProgramEntryRequirementRepositoryPort",
    "ProgramInfo",
    "ProgramInfoPort",
    "RepositoryError",
]
