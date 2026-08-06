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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from admissions.adapters.inbound.http.schemas import (
    AdmissionCycleResponse,
    AlternativeProgramPolicyResponse,
    ApplicantListResponse,
    ApplicantMatriculatedResponse,
    ApplicantNotQualifiedResponse,
    ApplicantQualifiedResponse,
    ApplicantResponse,
    NoOfferAvailableResponse,
    OfferDeclinedResponse,
    OfferMadeResponse,
    OfferResponse,
    OfferTakenUpResponse,
    OpenAdmissionCycleRequest,
    ProgramAdmissionsSummaryResponse,
    ProgramEntryRequirementResponse,
    PublishAlternativePolicyRequest,
    PublishEntryRequirementRequest,
    ScreeningResponse,
    SubmitApplicationRequest,
)
from admissions.application.accept_offer import AcceptOffer, AcceptOfferCommand
from admissions.application.decline_offer import DeclineOffer, DeclineOfferCommand
from admissions.application.list_program_applicants import (
    ListProgramApplicants,
    ListProgramApplicantsCommand,
)
from admissions.application.make_offer_to_applicant import (
    MakeOfferToApplicant,
    MakeOfferToApplicantCommand,
    OfferMade,
)
from admissions.application.matriculate_applicant import (
    MatriculateApplicant,
    MatriculateApplicantCommand,
)
from admissions.application.open_admission_cycle import (
    OpenAdmissionCycle,
    OpenAdmissionCycleCommand,
)
from admissions.application.publish_alternative_policy import (
    PublishAlternativePolicy,
    PublishAlternativePolicyCommand,
)
from admissions.application.publish_entry_requirement import (
    PublishEntryRequirement,
    PublishEntryRequirementCommand,
)
from admissions.application.read_policy import (
    ReadAdmissionCycle,
    ReadAlternativePolicy,
    ReadEntryRequirement,
)
from admissions.application.screen_applicant import (
    ApplicantQualified,
    ScreenApplicant,
    ScreenApplicantCommand,
)
from admissions.application.submit_application import SubmitApplication, SubmitApplicationCommand
from admissions.application.summarise_program_admissions import (
    SummariseProgramAdmissions,
    SummariseProgramAdmissionsCommand,
)
from admissions.application.views import (
    AdmissionCycleView,
    AlternativeProgramPolicyView,
    ApplicantView,
    ProgramAdmissionsSummaryView,
    ProgramEntryRequirementView,
)
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
        open_admission_cycle: OpenAdmissionCycle,
        publish_entry_requirement: PublishEntryRequirement,
        publish_alternative_policy: PublishAlternativePolicy,
        read_admission_cycle: ReadAdmissionCycle,
        read_entry_requirement: ReadEntryRequirement,
        read_alternative_policy: ReadAlternativePolicy,
        summarise_program_admissions: SummariseProgramAdmissions,
        list_program_applicants: ListProgramApplicants,
    ) -> None:
        self.submit_application = submit_application
        self.screen_applicant = screen_applicant
        self.make_offer_to_applicant = make_offer_to_applicant
        self.accept_offer = accept_offer
        self.decline_offer = decline_offer
        self.matriculate_applicant = matriculate_applicant
        self.open_admission_cycle = open_admission_cycle
        self.publish_entry_requirement = publish_entry_requirement
        self.publish_alternative_policy = publish_alternative_policy
        self.read_admission_cycle = read_admission_cycle
        self.read_entry_requirement = read_entry_requirement
        self.read_alternative_policy = read_alternative_policy
        self.summarise_program_admissions = summarise_program_admissions
        self.list_program_applicants = list_program_applicants


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


@router.post(
    "/admission-cycles",
    status_code=status.HTTP_201_CREATED,
    response_model=AdmissionCycleResponse,
    summary="Open a program's intake for a session",
    responses=error_responses(409, 422, 500, 503),
)
async def open_admission_cycle(
    body: OpenAdmissionCycleRequest, deps: Deps
) -> AdmissionCycleResponse:
    """Set the quota the whole offer flow is measured against.

    Set by the **department registrar** for their own programs. Before this route existed a
    quota could only be created by writing a row into Postgres by hand.

    A second cycle for the same program and session is a 409 rather than an overwrite: opening
    resets ``offers_made`` to zero, which would hand out places that are already held.

    **Unauthenticated in this phase**, so the departmental scope is not enforced anywhere.
    """
    cycle = await deps.open_admission_cycle.execute(
        OpenAdmissionCycleCommand(
            program_id=body.program_id, session_id=body.session_id, quota=body.quota
        )
    )
    return AdmissionCycleResponse.of(AdmissionCycleView.of(cycle))


@router.post(
    "/entry-requirements",
    status_code=status.HTTP_201_CREATED,
    response_model=ProgramEntryRequirementResponse,
    summary="Publish a program's entry requirement for a session",
    responses=error_responses(409, 422, 500, 503),
)
async def publish_entry_requirement(
    body: PublishEntryRequirementRequest, deps: Deps
) -> ProgramEntryRequirementResponse:
    """Write down the subject combination screening judges against.

    Set by the **department registrar**: a department knows what its own program needs.

    Republishing is a 409, not an overwrite — a cohort part-way through screening must not be
    judged against two different rules. Publishing next session's requirement is a different
    key and leaves this one readable.
    """
    requirement = await deps.publish_entry_requirement.execute(
        PublishEntryRequirementCommand(
            program_id=body.program_id,
            session_id=body.session_id,
            required_subjects=body.required_subjects,
            one_of_groups=body.one_of_groups,
        )
    )
    return ProgramEntryRequirementResponse.of(ProgramEntryRequirementView.of(requirement))


@router.post(
    "/alternative-policies",
    status_code=status.HTTP_201_CREATED,
    response_model=AlternativeProgramPolicyResponse,
    summary="Publish a program's alternative-program chain for a session",
    responses=error_responses(409, 422, 500, 503),
)
async def publish_alternative_policy(
    body: PublishAlternativePolicyRequest, deps: Deps
) -> AlternativeProgramPolicyResponse:
    """Write down where a program overflows to, in preference order.

    Owned by a **faculty officer** rather than a department registrar, because a chain names
    other departments' programs and spends *their* quota. That ownership is a decision
    recorded in CLAUDE.md section 6 and **not enforced here** — there is no authentication,
    and checking that every program named sits in the writer's faculty is a cross-context read
    Admissions cannot make today. Both arrive with identity.

    Order is the whole content of the chain: first qualifying program with a place left takes
    the applicant.
    """
    policy = await deps.publish_alternative_policy.execute(
        PublishAlternativePolicyCommand(
            program_id=body.program_id,
            session_id=body.session_id,
            alternatives=body.alternatives,
        )
    )
    return AlternativeProgramPolicyResponse.of(AlternativeProgramPolicyView.of(policy))


# ---- the registrar's read model ----

SessionQuery = Annotated[str, Query(description="The session the question is asked about.")]


@router.get(
    "/programs/{program_id}/admissions-summary",
    response_model=ProgramAdmissionsSummaryResponse,
    summary="A program's quota and the state of everyone who applied to it",
    responses=error_responses(422, 500, 503),
)
async def summarise_program_admissions(
    program_id: str, session_id: SessionQuery, deps: Deps
) -> ProgramAdmissionsSummaryResponse:
    """The registrar's dashboard for one program.

    **The two halves count different populations and will not add up.** ``offers_made`` counts
    places claimed on this program, including by applicants who applied elsewhere and
    overflowed here through another program's fallback chain. The funnel counts applicants who
    applied *to* this program, including ones placed somewhere else. A registrar needs both:
    one is capacity, the other is cohort.

    Never a 404. A program with no cycle and no applicants is a summary of zeroes and nulls,
    which is a truthful answer to "how is this program doing" rather than a missing thing.
    """
    summary = await deps.summarise_program_admissions.execute(
        SummariseProgramAdmissionsCommand(program_id=program_id, session_id=session_id)
    )
    return ProgramAdmissionsSummaryResponse.of(ProgramAdmissionsSummaryView.of(summary))


@router.get(
    "/programs/{program_id}/applicants",
    response_model=ApplicantListResponse,
    summary="The applicants for a program, optionally by status",
    responses=error_responses(422, 500, 503),
)
async def list_program_applicants(
    program_id: str,
    session_id: SessionQuery,
    deps: Deps,
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="One application status, e.g. screened."),
    ] = None,
) -> ApplicantListResponse:
    """Everyone who **applied to** this program, whatever they were eventually offered.

    Keyed on the applied program rather than the offered one because it never changes: a
    registrar's working list must not silently lose somebody the moment the offer flow places
    them elsewhere. People placed *here* from another program's chain appear in the capacity
    half of the summary instead.

    An unrecognised ``status`` is a 422 rather than an empty list — a typo answering the same
    as "no applicants" is one a registrar would act on.
    """
    applicants = await deps.list_program_applicants.execute(
        ListProgramApplicantsCommand(
            program_id=program_id, session_id=session_id, status=status_filter
        )
    )
    return ApplicantListResponse(
        applicants=tuple(
            ApplicantResponse.of(ApplicantView.of(applicant)) for applicant in applicants
        )
    )


@router.get(
    "/programs/{program_id}/admission-cycle",
    response_model=AdmissionCycleResponse,
    summary="Read a program's intake for a session",
    responses=error_responses(404, 422, 500, 503),
)
async def read_admission_cycle(
    program_id: str, session_id: SessionQuery, deps: Deps
) -> AdmissionCycleResponse:
    """Quota, places claimed and places left, as the aggregate derives them."""
    cycle = await deps.read_admission_cycle.find(program_id, session_id)
    if cycle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no admission cycle for program {program_id!r} in session {session_id!r}",
        )
    return AdmissionCycleResponse.of(AdmissionCycleView.of(cycle))


@router.get(
    "/programs/{program_id}/entry-requirement",
    response_model=ProgramEntryRequirementResponse,
    summary="Read a program's entry requirement for a session",
    responses=error_responses(404, 422, 500, 503),
)
async def read_entry_requirement(
    program_id: str, session_id: SessionQuery, deps: Deps
) -> ProgramEntryRequirementResponse:
    """What screening will judge against. A 404 means nobody has published one."""
    requirement = await deps.read_entry_requirement.find(program_id, session_id)
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no entry requirement for program {program_id!r} in session {session_id!r}",
        )
    return ProgramEntryRequirementResponse.of(ProgramEntryRequirementView.of(requirement))


@router.get(
    "/programs/{program_id}/alternative-policy",
    response_model=AlternativeProgramPolicyResponse,
    summary="Read a program's alternative-program chain for a session",
    responses=error_responses(404, 422, 500, 503),
)
async def read_alternative_policy(
    program_id: str, session_id: SessionQuery, deps: Deps
) -> AlternativeProgramPolicyResponse:
    """Where this program overflows to, in the order the offer flow will walk.

    A 404 means nobody published a chain; an empty ``alternatives`` means somebody published
    one that says nowhere. The offer flow treats those identically and a registrar should not
    have to — they are different states of the work.
    """
    policy = await deps.read_alternative_policy.find(program_id, session_id)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no alternative policy for program {program_id!r} in session {session_id!r}",
        )
    return AlternativeProgramPolicyResponse.of(AlternativeProgramPolicyView.of(policy))


__all__ = ["STATE_KEY", "AdmissionsDependencies", "router"]
