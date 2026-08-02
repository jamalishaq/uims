"""Admissions application layer.

Orchestration only. Every use case here loads through a port, delegates each decision to
the domain, and persists — whether an applicant may be screened is the ``Applicant``
aggregate's rule, and whether their subjects qualify them is
``SubjectCombinationRule``'s. Neither is restated here.

Domain errors pass through untranslated: :class:`ApplicantAlreadyScreenedError` reaching a
caller unchanged is the point, because the domain has already said exactly what went wrong
and rewrapping it would only lose that.

The verdicts, though, are returned rather than raised. ``ApplicantNotQualified`` is what a
use case hands back when the university's answer is no, and ``QuotaExhausted`` will be
what the offer flow hands back when a program is full (CLAUDE.md section 3). Errors here
mean a use case could not do its job; outcomes mean it did, and the answer was no.
"""

from admissions.application.errors import (
    ApplicantNotFoundError,
    ApplicationError,
    EntryRequirementNotFoundError,
)
from admissions.application.screen_applicant import (
    ApplicantNotQualified,
    ApplicantQualified,
    ScreenApplicant,
    ScreenApplicantCommand,
    ScreeningOutcome,
)

__all__ = [
    "ApplicantNotFoundError",
    "ApplicantNotQualified",
    "ApplicantQualified",
    "ApplicationError",
    "EntryRequirementNotFoundError",
    "ScreenApplicant",
    "ScreenApplicantCommand",
    "ScreeningOutcome",
]
