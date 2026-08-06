"""Admissions application layer.

Orchestration only. Every use case here loads through a port, delegates each decision to
the domain, and persists — whether an applicant may be screened is the ``Applicant``
aggregate's rule, whether their subjects qualify them is ``SubjectCombinationRule``'s, and
whether a program still has a place is ``AdmissionCycle``'s. None of them is restated here.

What *is* here, and is here because no aggregate could hold it, is the order the questions
are asked in. ``MakeOfferToApplicant`` tries the applied program, then walks the fallback
chain: deciding what to ask next means knowing about two aggregates at once, and knowing
about two aggregates at once is precisely what an aggregate may not do. Each write stays
in its own transaction (CLAUDE.md section 4) — the sequence is orchestration, never one
big commit.

Domain errors pass through untranslated: :class:`ApplicantAlreadyScreenedError` reaching a
caller unchanged is the point, because the domain has already said exactly what went wrong
and rewrapping it would only lose that.

The verdicts, though, are returned rather than raised. ``ApplicantNotQualified`` is what a
use case hands back when the university's answer is no, and ``NoOfferAvailable`` is what
the offer flow hands back when every program the applicant could go to was full. Errors
here mean a use case could not do its job; outcomes mean it did, and the answer was no.
"""

from admissions.application.accept_offer import AcceptOffer, AcceptOfferCommand, OfferTakenUp
from admissions.application.decline_offer import DeclineOffer, DeclineOfferCommand, OfferDeclined
from admissions.application.errors import (
    AdmissionCycleNotFoundError,
    ApplicantNotFoundError,
    ApplicationError,
    EntryRequirementNotFoundError,
    ProgramNotAdmittingError,
    ProgramNotFoundError,
)
from admissions.application.make_offer_to_applicant import (
    MakeOfferToApplicant,
    MakeOfferToApplicantCommand,
    NoOfferAvailable,
    OfferDecision,
    OfferMade,
)
from admissions.application.matriculate_applicant import (
    ApplicantMatriculated,
    MatriculateApplicant,
    MatriculateApplicantCommand,
)
from admissions.application.record_acceptance_fee_paid import (
    AcceptanceFeeRecorded,
    RecordAcceptanceFeePaid,
    RecordAcceptanceFeePaidCommand,
)
from admissions.application.screen_applicant import (
    ApplicantNotQualified,
    ApplicantQualified,
    ScreenApplicant,
    ScreenApplicantCommand,
    ScreeningOutcome,
)
from admissions.application.submit_application import SubmitApplication, SubmitApplicationCommand
from admissions.application.views import ApplicantView, UtmeSubjectScoreView

__all__ = [
    "AcceptOffer",
    "AcceptOfferCommand",
    "AcceptanceFeeRecorded",
    "AdmissionCycleNotFoundError",
    "ApplicantMatriculated",
    "ApplicantNotFoundError",
    "ApplicantNotQualified",
    "ApplicantQualified",
    "ApplicantView",
    "ApplicationError",
    "DeclineOffer",
    "DeclineOfferCommand",
    "EntryRequirementNotFoundError",
    "MakeOfferToApplicant",
    "MakeOfferToApplicantCommand",
    "MatriculateApplicant",
    "MatriculateApplicantCommand",
    "NoOfferAvailable",
    "OfferDecision",
    "OfferDeclined",
    "OfferMade",
    "OfferTakenUp",
    "ProgramNotAdmittingError",
    "ProgramNotFoundError",
    "RecordAcceptanceFeePaid",
    "RecordAcceptanceFeePaidCommand",
    "ScreenApplicant",
    "ScreenApplicantCommand",
    "ScreeningOutcome",
    "SubmitApplication",
    "SubmitApplicationCommand",
    "UtmeSubjectScoreView",
]
