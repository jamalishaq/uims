"""HTTP routes for Admissions: apply, screen, and decide an offer.

Three routes for the three use cases that exist. There is no accept-offer route and no
matriculate route, and that is not an oversight of this phase: ``Applicant.accept()`` and
``Applicant.matriculate()`` are domain methods with no use case in front of them, and CLAUDE.md
section 3 is explicit that matriculation "is a human-triggered use case that checks the flag".
Writing the route would mean writing the use case, which is a different change.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from admissions.adapters.inbound.http.schemas import (
    ApplicantNotQualifiedResponse,
    ApplicantQualifiedResponse,
    ApplicantResponse,
    NoOfferAvailableResponse,
    OfferMadeResponse,
    OfferResponse,
    ScreeningResponse,
    SubmitApplicationRequest,
)
from admissions.application.make_offer_to_applicant import (
    MakeOfferToApplicant,
    MakeOfferToApplicantCommand,
    OfferMade,
)
from admissions.application.screen_applicant import (
    ApplicantQualified,
    ScreenApplicant,
    ScreenApplicantCommand,
)
from admissions.application.submit_application import SubmitApplication, SubmitApplicationCommand
from admissions.application.views import ApplicantView
from http_api import dependencies_of, error_responses

STATE_KEY = "admissions"
"""Where this context's use cases hang on ``app.state``. Owned here, read by the root."""


class AdmissionsDependencies:
    """The use cases this router needs, wired once at startup."""

    def __init__(
        self,
        submit_application: SubmitApplication,
        screen_applicant: ScreenApplicant,
        make_offer_to_applicant: MakeOfferToApplicant,
    ) -> None:
        self.submit_application = submit_application
        self.screen_applicant = screen_applicant
        self.make_offer_to_applicant = make_offer_to_applicant


def _deps(request: Request) -> AdmissionsDependencies:
    return dependencies_of(request, STATE_KEY, AdmissionsDependencies)


Deps = Annotated[AdmissionsDependencies, Depends(_deps)]

router = APIRouter(prefix="/admissions", tags=["admissions"])


@router.post(
    "/applications",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicantResponse,
    summary="Submit an application",
    responses=error_responses(404, 409, 422, 500, 503),
)
async def submit_application(body: SubmitApplicationRequest, deps: Deps) -> ApplicantResponse:
    """File an application, once the program is confirmed to exist and be admitting."""
    applicant = await deps.submit_application.execute(
        SubmitApplicationCommand(
            applicant_id=body.applicant_id,
            program_id=body.program_id,
            session_id=body.session_id,
            full_name=body.full_name,
            utme_scores=tuple((score.subject, score.score) for score in body.utme_scores),
            date_of_birth=body.date_of_birth,
            email=body.email,
            phone_number=body.phone_number,
        )
    )
    return ApplicantResponse.of(ApplicantView.of(applicant))


@router.post(
    "/applicants/{applicant_id}/screening",
    response_model=ScreeningResponse,
    summary="Screen an applicant against their program's entry requirement",
    responses=error_responses(404, 409, 422, 500, 503),
)
async def screen_applicant(applicant_id: str, deps: Deps) -> ScreeningResponse:
    """Screen, and say so either way.

    Failing to qualify is a decision about a candidate, not a bad request — so both answers
    are 200 and the body says which, tagged by ``outcome``.
    """
    outcome = await deps.screen_applicant.execute(ScreenApplicantCommand(applicant_id=applicant_id))
    if isinstance(outcome, ApplicantQualified):
        return ApplicantQualifiedResponse.of(outcome)
    return ApplicantNotQualifiedResponse.of(outcome)


@router.post(
    "/applicants/{applicant_id}/offer",
    response_model=OfferResponse,
    summary="Decide an applicant's offer, falling back to alternative programs",
    responses=error_responses(404, 409, 422, 500, 503),
)
async def make_offer_to_applicant(applicant_id: str, deps: Deps) -> OfferResponse:
    """Try the applied program, then each qualifying alternative in preference order.

    A full quota never reaches this route as an error: it is a normal outcome the use case
    handles by moving to the next alternative, and only the exhaustion of *all* of them
    produces ``no_offer_available``.
    """
    decision = await deps.make_offer_to_applicant.execute(
        MakeOfferToApplicantCommand(applicant_id=applicant_id)
    )
    if isinstance(decision, OfferMade):
        return OfferMadeResponse.of(decision)
    return NoOfferAvailableResponse.of(decision)


__all__ = ["STATE_KEY", "AdmissionsDependencies", "router"]
