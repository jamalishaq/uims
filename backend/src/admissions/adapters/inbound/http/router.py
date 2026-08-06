"""HTTP routes for Admissions: apply, screen, decide an offer, answer it, matriculate.

Six routes covering an application's whole life. The three that arrived last —
acceptance, declination, matriculation — close a chain that used to stop dead after the
offer decision: with nothing able to accept, ``OfferAccepted`` was never published, no
ledger was ever opened, and no applicant could become a student.

**There is no reject route, and that is a decision rather than a gap.** An application ends
without a place exactly two ways, both automatic: screening finds the applicant unqualified,
or every cycle in the fallback chain is full. ``record_no_offer()`` is reachable only from
those two flows, so a registrar cannot turn down somebody the rules would have admitted.

**Accepting and declining are the applicant's own acts**, which is why neither route names an
actor. ``decline()`` is terminal, and an offer let go by the wrong hand cannot be given back.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from admissions.adapters.inbound.http.schemas import (
    ApplicantMatriculatedResponse,
    ApplicantNotQualifiedResponse,
    ApplicantQualifiedResponse,
    ApplicantResponse,
    NoOfferAvailableResponse,
    OfferDeclinedResponse,
    OfferMadeResponse,
    OfferResponse,
    OfferTakenUpResponse,
    ScreeningResponse,
    SubmitApplicationRequest,
)
from admissions.application.accept_offer import AcceptOffer, AcceptOfferCommand
from admissions.application.decline_offer import DeclineOffer, DeclineOfferCommand
from admissions.application.make_offer_to_applicant import (
    MakeOfferToApplicant,
    MakeOfferToApplicantCommand,
    OfferMade,
)
from admissions.application.matriculate_applicant import (
    MatriculateApplicant,
    MatriculateApplicantCommand,
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
        accept_offer: AcceptOffer,
        decline_offer: DeclineOffer,
        matriculate_applicant: MatriculateApplicant,
    ) -> None:
        self.submit_application = submit_application
        self.screen_applicant = screen_applicant
        self.make_offer_to_applicant = make_offer_to_applicant
        self.accept_offer = accept_offer
        self.decline_offer = decline_offer
        self.matriculate_applicant = matriculate_applicant


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


@router.post(
    "/applicants/{applicant_id}/acceptance",
    status_code=status.HTTP_201_CREATED,
    response_model=OfferTakenUpResponse,
    summary="Accept an offer",
    responses=error_responses(404, 409, 422, 500, 503),
)
async def accept_offer(applicant_id: str, deps: Deps) -> OfferTakenUpResponse:
    """Take up the offered place. This is what opens the applicant's ledger.

    201 rather than 200: acceptance creates something that did not exist before — an account
    in Billing, with both admission charges raised against it.

    **Unauthenticated in this phase.** Anybody who can reach the process can accept on
    anybody's behalf, and the counterpart declination is terminal. Identity closes this.
    """
    taken_up = await deps.accept_offer.execute(AcceptOfferCommand(applicant_id=applicant_id))
    return OfferTakenUpResponse.of(taken_up)


@router.post(
    "/applicants/{applicant_id}/declination",
    response_model=OfferDeclinedResponse,
    summary="Decline an offer, returning the place to the quota",
    responses=error_responses(404, 409, 422, 500, 503),
)
async def decline_offer(applicant_id: str, deps: Deps) -> OfferDeclinedResponse:
    """Turn the place down. Terminal for the applicant, and the cycle gets the place back.

    200 rather than 201: nothing is created. What changes is a count on a cycle that already
    existed, and the response reports it.

    **Unauthenticated in this phase**, and this is the route where that matters most: an
    offer declined cannot be un-declined.
    """
    declined = await deps.decline_offer.execute(DeclineOfferCommand(applicant_id=applicant_id))
    return OfferDeclinedResponse.of(declined)


@router.post(
    "/applicants/{applicant_id}/matriculation",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicantMatriculatedResponse,
    summary="Matriculate an accepted, fee-cleared applicant",
    responses=error_responses(404, 409, 422, 500, 503),
)
async def matriculate_applicant(applicant_id: str, deps: Deps) -> ApplicantMatriculatedResponse:
    """Turn the applicant into a student. Human-triggered, never automatic on payment.

    201, because a student now exists in Student Profile with a matric number issued.

    The acceptance fee gates this and an outstanding matriculation fee does not — CLAUDE.md
    section 4, and the aggregate enforces it rather than this route. A 409 here means the
    applicant has not accepted, or the gating fee has not cleared.
    """
    matriculated = await deps.matriculate_applicant.execute(
        MatriculateApplicantCommand(applicant_id=applicant_id)
    )
    return ApplicantMatriculatedResponse.of(matriculated)


__all__ = ["STATE_KEY", "AdmissionsDependencies", "router"]
