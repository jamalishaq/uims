"""Admissions domain layer.

Owns an applicant's passage from application to matriculation: the ``Applicant``
aggregate and the state machine it enforces, plus the bio-data and UTME value objects an
application is made of. Owns, too, the two judgements made about an application from
outside it — whether a program still has a place (``AdmissionCycle``), whether an
applicant's subjects qualify them for one (``ProgramEntryRequirement`` and
``SubjectCombinationRule``), and where a full program overflows to
(``AlternativeProgramPolicy``). Stdlib only: no persistence, no ports, no HTTP reaches
this package.

Neither of those judgements says no by raising. ``QuotaExhausted`` is an outcome (see
``outcomes.py``) and an unmet requirement is a verdict, because a full program and an
unqualified applicant are how admissions normally ends for most of the people who apply
(CLAUDE.md section 3).
"""

from admissions.domain.admission_cycle import AdmissionCycle
from admissions.domain.alternative_program_policy import AlternativeProgramPolicy
from admissions.domain.applicant import Applicant, ApplicationStatus
from admissions.domain.entry_requirement import ProgramEntryRequirement, SubjectGroup
from admissions.domain.errors import (
    AcceptanceFeeNotClearedError,
    AdmissionsError,
    ApplicantAlreadyScreenedError,
    ApplicantNotScreenedError,
    ApplicationOutcomeFinalError,
    DuplicateAlternativeError,
    InvalidBioDataError,
    InvalidOffersMadeError,
    InvalidQuotaError,
    InvalidSubjectGroupError,
    InvalidUtmeResultError,
    InvalidUtmeScoreError,
    MissingIdentifierError,
    NoOfferToRespondToError,
    OfferAlreadyMadeError,
    OfferAlreadyRespondedToError,
    OfferNotAcceptedError,
    OverlappingRequirementError,
    SelfReferentialAlternativeError,
    UnsatisfiableRequirementError,
)
from admissions.domain.outcomes import OfferOutcome, OfferRecorded, QuotaExhausted
from admissions.domain.subject_combination_rule import SubjectCombinationRule
from admissions.domain.values import UTME_SUBJECT_COUNT, BioData, UtmeResult, UtmeSubjectScore

__all__ = [
    "UTME_SUBJECT_COUNT",
    "AcceptanceFeeNotClearedError",
    "AdmissionCycle",
    "AdmissionsError",
    "AlternativeProgramPolicy",
    "Applicant",
    "ApplicantAlreadyScreenedError",
    "ApplicantNotScreenedError",
    "ApplicationOutcomeFinalError",
    "ApplicationStatus",
    "BioData",
    "DuplicateAlternativeError",
    "InvalidBioDataError",
    "InvalidOffersMadeError",
    "InvalidQuotaError",
    "InvalidSubjectGroupError",
    "InvalidUtmeResultError",
    "InvalidUtmeScoreError",
    "MissingIdentifierError",
    "NoOfferToRespondToError",
    "OfferAlreadyMadeError",
    "OfferAlreadyRespondedToError",
    "OfferNotAcceptedError",
    "OfferOutcome",
    "OfferRecorded",
    "OverlappingRequirementError",
    "ProgramEntryRequirement",
    "QuotaExhausted",
    "SelfReferentialAlternativeError",
    "SubjectCombinationRule",
    "SubjectGroup",
    "UnsatisfiableRequirementError",
    "UtmeResult",
    "UtmeSubjectScore",
]
