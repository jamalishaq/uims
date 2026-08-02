"""Admissions ports layer.

The interfaces the outside world plugs into: persistence for the ``Applicant`` aggregate
and for this context's own entry-requirement policy, plus the failures that persistence is
allowed to express.

Not here yet, and deliberately: ``ProgramInfoPort`` (the query to Faculty & Department) and
the event publisher this context announces ``OfferAccepted`` and ``StudentMatriculated``
through arrive with the offer flow (CLAUDE.md section 3). Screening needs neither — it
reads an application and a rule this context already owns.
"""

from admissions.ports.applicant_repository import ApplicantRepositoryPort
from admissions.ports.entry_requirement_repository import ProgramEntryRequirementRepositoryPort
from admissions.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    RepositoryError,
)

__all__ = [
    "AggregateNotFoundError",
    "ApplicantRepositoryPort",
    "DuplicateAggregateError",
    "ProgramEntryRequirementRepositoryPort",
    "RepositoryError",
]
