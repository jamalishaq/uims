"""Admissions domain layer.

Owns an applicant's passage from application to matriculation: the ``Applicant``
aggregate and the state machine it enforces, plus the bio-data and UTME value objects an
application is made of. Stdlib only: no persistence, no ports, no HTTP reaches this
package.
"""

from admissions.domain.applicant import Applicant, ApplicationStatus
from admissions.domain.errors import (
    AcceptanceFeeNotClearedError,
    AdmissionsError,
    ApplicantAlreadyScreenedError,
    ApplicantNotScreenedError,
    ApplicationOutcomeFinalError,
    InvalidBioDataError,
    InvalidUtmeResultError,
    InvalidUtmeScoreError,
    MissingIdentifierError,
    NoOfferToRespondToError,
    OfferAlreadyMadeError,
    OfferAlreadyRespondedToError,
    OfferNotAcceptedError,
)
from admissions.domain.values import BioData, UtmeResult, UtmeSubjectScore

__all__ = [
    "AcceptanceFeeNotClearedError",
    "AdmissionsError",
    "Applicant",
    "ApplicantAlreadyScreenedError",
    "ApplicantNotScreenedError",
    "ApplicationOutcomeFinalError",
    "ApplicationStatus",
    "BioData",
    "InvalidBioDataError",
    "InvalidUtmeResultError",
    "InvalidUtmeScoreError",
    "MissingIdentifierError",
    "NoOfferToRespondToError",
    "OfferAlreadyMadeError",
    "OfferAlreadyRespondedToError",
    "OfferNotAcceptedError",
    "UtmeResult",
    "UtmeSubjectScore",
]
