"""Admissions ports layer.

The interfaces the outside world plugs into: persistence for the ``Applicant`` and
``AdmissionCycle`` aggregates and for this context's own session-scoped policy — entry
requirements and alternative-program chains — plus the one query this context makes of
another. ``ProgramInfoPort`` asks Faculty & Department whether a program exists and is
admitting, checked at application time (CLAUDE.md section 3), and answers in a type
defined here rather than there.

``EventPublisherPort`` is how this context announces ``OfferAccepted`` and
``StudentMatriculated``, the two facts CLAUDE.md section 3 says Admissions publishes. It was
absent for five phases because neither event had a producer: an offer being *made* is not
among them, and the acceptance and matriculation flows that do produce them did not exist.
They exist now, and the two handlers that were waiting on the other side of the bus —
Billing's ``OfferAcceptedHandler`` and Student Profile's ``StudentMatriculatedHandler`` —
finally have something to receive.
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
from admissions.ports.event_publisher import EventPublisherPort
from admissions.ports.program_info import ProgramInfo, ProgramInfoPort

__all__ = [
    "AdmissionCycleRepositoryPort",
    "AggregateNotFoundError",
    "AlternativeProgramPolicyRepositoryPort",
    "ApplicantRepositoryPort",
    "DuplicateAggregateError",
    "EventPublisherPort",
    "PersistenceUnavailableError",
    "ProgramEntryRequirementRepositoryPort",
    "ProgramInfo",
    "ProgramInfoPort",
    "RepositoryError",
]
