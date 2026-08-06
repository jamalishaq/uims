"""Pydantic request and response models. They go no further than this package.

Two of the three responses are discriminated unions, for Enrollment's reason: screening and
offer-making both end two ways, neither of which is an error.

The UTME result is the one request shape worth reading twice. Four subjects and their scores
arrive as a list of objects rather than a mapping, because a mapping would silently accept
three subjects with a repeat and hand the domain something it has to reject anyway — and
because the order a candidate sat them in is the order the form shows. Whether four *distinct*
subjects, each scored 0 to 100, is a valid combination is ``UtmeResult``'s judgement, and it is not
restated here beyond the bounds that stop a negative number reaching it.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from admissions.application.accept_offer import OfferTakenUp
from admissions.application.decline_offer import OfferDeclined
from admissions.application.make_offer_to_applicant import NoOfferAvailable, OfferMade
from admissions.application.matriculate_applicant import ApplicantMatriculated
from admissions.application.screen_applicant import ApplicantNotQualified, ApplicantQualified
from admissions.application.views import (
    AdmissionCycleView,
    AlternativeProgramPolicyView,
    ApplicantView,
    ProgramAdmissionsSummaryView,
    ProgramEntryRequirementView,
    UtmeSubjectScoreView,
)


class UtmeSubjectScoreSchema(BaseModel):
    """One subject and what it scored."""

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, description="Upper-cased by the domain.")
    score: int = Field(ge=0, le=100)

    @classmethod
    def of(cls, view: UtmeSubjectScoreView) -> "UtmeSubjectScoreSchema":
        return cls(**vars(view))


class SubmitApplicationRequest(BaseModel):
    """An application for a place.

    ``session_id`` is required and carries no default: the program must be admitting *for a
    session*, and a form that left it out would be checked against the wrong one.
    """

    model_config = ConfigDict(extra="forbid")

    applicant_id: str = Field(min_length=1)
    program_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    utme_scores: tuple[UtmeSubjectScoreSchema, ...]
    date_of_birth: date | None = None
    email: str | None = None
    phone_number: str | None = None


class ApplicantResponse(BaseModel):
    """One application, as Admissions holds it."""

    applicant_id: str
    applied_program_id: str
    offered_program_id: str | None
    session_id: str
    status: str
    is_fee_cleared: bool
    is_final: bool
    full_name: str
    date_of_birth: date | None
    email: str | None
    phone_number: str | None
    utme_scores: tuple[UtmeSubjectScoreSchema, ...]
    utme_aggregate: int

    @classmethod
    def of(cls, view: ApplicantView) -> "ApplicantResponse":
        return cls(
            **(
                vars(view)
                | {"utme_scores": tuple(map(UtmeSubjectScoreSchema.of, view.utme_scores))}
            )
        )


class ApplicantQualifiedResponse(BaseModel):
    """The applicant's subjects satisfy the program's entry requirement."""

    outcome: Literal["qualified"] = "qualified"
    applicant_id: str
    program_id: str

    @classmethod
    def of(cls, qualified: ApplicantQualified) -> "ApplicantQualifiedResponse":
        return cls(applicant_id=qualified.applicant_id, program_id=qualified.program_id)


class ApplicantNotQualifiedResponse(BaseModel):
    """They do not, and ``unmet`` says what was missing."""

    outcome: Literal["not_qualified"] = "not_qualified"
    applicant_id: str
    program_id: str
    unmet: tuple[str, ...]

    @classmethod
    def of(cls, not_qualified: ApplicantNotQualified) -> "ApplicantNotQualifiedResponse":
        return cls(
            applicant_id=not_qualified.applicant_id,
            program_id=not_qualified.program_id,
            unmet=not_qualified.unmet,
        )


ScreeningResponse = ApplicantQualifiedResponse | ApplicantNotQualifiedResponse
"""Both ways screening can end, tagged by ``outcome``."""


class OfferMadeResponse(BaseModel):
    """A place was found. ``is_alternative`` is true when it is not the program applied for."""

    outcome: Literal["offer_made"] = "offer_made"
    applicant_id: str
    program_id: str
    applied_program_id: str
    is_alternative: bool

    @classmethod
    def of(cls, made: OfferMade) -> "OfferMadeResponse":
        return cls(
            applicant_id=made.applicant_id,
            program_id=made.program_id,
            applied_program_id=made.applied_program_id,
            is_alternative=made.is_alternative,
        )


class NoOfferAvailableResponse(BaseModel):
    """No place was found, and ``considered`` lists every program that was tried."""

    outcome: Literal["no_offer_available"] = "no_offer_available"
    applicant_id: str
    applied_program_id: str
    considered: tuple[str, ...]

    @classmethod
    def of(cls, none_available: NoOfferAvailable) -> "NoOfferAvailableResponse":
        return cls(
            applicant_id=none_available.applicant_id,
            applied_program_id=none_available.applied_program_id,
            considered=none_available.considered,
        )


OfferResponse = OfferMadeResponse | NoOfferAvailableResponse
"""Both ways an offer decision can end, tagged by ``outcome``."""


class OfferTakenUpResponse(BaseModel):
    """The applicant accepted, and their ledger has been opened.

    Not a discriminated union, unlike the two above: accepting has one ending. Every other
    way this request can go is a refusal by the aggregate, and those leave as 4xx.
    """

    applicant_id: str
    program_id: str
    session_id: str

    @classmethod
    def of(cls, taken_up: OfferTakenUp) -> "OfferTakenUpResponse":
        return cls(**vars(taken_up))


class OfferDeclinedResponse(BaseModel):
    """The applicant turned the place down, and the cycle has it back.

    ``places_remaining`` is the figure the decline actually moved, reported because a
    registrar watching a program fill up is watching exactly this number.
    """

    applicant_id: str
    program_id: str
    session_id: str
    places_remaining: int

    @classmethod
    def of(cls, declined: OfferDeclined) -> "OfferDeclinedResponse":
        return cls(**vars(declined))


class ApplicantMatriculatedResponse(BaseModel):
    """The application is closed and a student exists.

    No matric number, because this context never learns it — issuing one is Student Profile's
    job and nothing is published back (CLAUDE.md section 3). A client that needs the number
    reads it from Student Profile, which is the context that owns it.
    """

    applicant_id: str
    program_id: str
    session_id: str

    @classmethod
    def of(cls, matriculated: ApplicantMatriculated) -> "ApplicantMatriculatedResponse":
        return cls(**vars(matriculated))


# ---- the session-scoped policy a registrar writes before a cycle runs ----


class OpenAdmissionCycleRequest(BaseModel):
    """A program's intake for a session.

    ``quota`` is ``ge=0`` rather than ``gt=0``: zero is a meaningful policy — a program that
    is not admitting this session — and the domain treats such a cycle as full from the moment
    it opens.
    """

    model_config = ConfigDict(extra="forbid")

    program_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    quota: int = Field(ge=0)


class AdmissionCycleResponse(BaseModel):
    """One program's intake, and how much of it is left."""

    program_id: str
    session_id: str
    quota: int
    offers_made: int
    places_remaining: int
    is_full: bool

    @classmethod
    def of(cls, view: AdmissionCycleView) -> "AdmissionCycleResponse":
        return cls(**vars(view))


class PublishEntryRequirementRequest(BaseModel):
    """What a program demands of an applicant's four UTME subjects.

    Neither list is bounded here. How many demands a result can satisfy is the domain's rule
    — four distinct subjects — and restating it as a schema constraint would put the same
    number in two places, to disagree the day it changes.
    """

    model_config = ConfigDict(extra="forbid")

    program_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    required_subjects: tuple[str, ...] = ()
    one_of_groups: tuple[tuple[str, ...], ...] = ()


class ProgramEntryRequirementResponse(BaseModel):
    """The published requirement. Subjects come back upper-cased and sorted."""

    program_id: str
    session_id: str
    required_subjects: tuple[str, ...]
    one_of_groups: tuple[tuple[str, ...], ...]

    @classmethod
    def of(cls, view: ProgramEntryRequirementView) -> "ProgramEntryRequirementResponse":
        return cls(**vars(view))


class PublishAlternativePolicyRequest(BaseModel):
    """Where a program overflows to, best first.

    A list rather than a set, and the order is the policy: the first qualifying program with a
    place left takes the applicant.
    """

    model_config = ConfigDict(extra="forbid")

    program_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    alternatives: tuple[str, ...] = ()


class AlternativeProgramPolicyResponse(BaseModel):
    """The published chain, in the order it will be walked."""

    program_id: str
    session_id: str
    alternatives: tuple[str, ...]

    @classmethod
    def of(cls, view: AlternativeProgramPolicyView) -> "AlternativeProgramPolicyResponse":
        return cls(**vars(view))


class ApplicantListResponse(BaseModel):
    """The applicants for one program. An empty list is a normal answer."""

    applicants: tuple[ApplicantResponse, ...]


class ProgramAdmissionsSummaryResponse(BaseModel):
    """A registrar's view of one program: capacity above, cohort below.

    **The two halves count different populations and will not reconcile.** ``offers_made``
    counts places claimed *on this program*, including by applicants who applied elsewhere and
    overflowed here through another program's fallback chain. The funnel counts applicants who
    *applied to* this program, including ones offered a place somewhere else. Both are needed
    and neither is the other.

    The capacity fields are ``null`` when no cycle has been opened — a real state, and one that
    reporting as zero would render as "full".
    """

    program_id: str
    session_id: str
    quota: int | None
    offers_made: int | None
    places_remaining: int | None
    is_full: bool | None
    applied: int
    screened: int
    offered: int
    accepted: int
    declined: int
    matriculated: int
    no_offer_available: int
    total_applicants: int

    @classmethod
    def of(cls, view: ProgramAdmissionsSummaryView) -> "ProgramAdmissionsSummaryResponse":
        return cls(**vars(view))
