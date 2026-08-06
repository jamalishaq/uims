"""Primitives-shaped projections of what this context's use cases return.

``SubmitApplication`` hands back the ``Applicant`` aggregate, which is the right answer for a
caller inside the application layer and the wrong one for anything past it: the aggregate
carries ``accept``, ``decline`` and ``matriculate``, and a transport holding it is a transport
that can advance somebody's application by accident.

Flattening lives here rather than in the HTTP adapter because it needs to know what an
application *is* — that a status is an enum whose value is the wire form, that four UTME
subject scores make an aggregate, that ``offered_program_id`` may differ from the applied one
and is ``None`` until an offer is made. See ``course_catalog/application/views.py`` for the
same argument at length.
"""

from dataclasses import dataclass
from datetime import date

from admissions.domain.admission_cycle import AdmissionCycle
from admissions.domain.alternative_program_policy import AlternativeProgramPolicy
from admissions.domain.applicant import Applicant
from admissions.domain.entry_requirement import ProgramEntryRequirement


@dataclass(frozen=True)
class UtmeSubjectScoreView:
    """One subject and what it scored."""

    subject: str
    score: int


@dataclass(frozen=True)
class ApplicantView:
    """One application, flat.

    ``aggregate`` is derived by ``UtmeResult`` rather than summed here, so the number reported
    is the number the screening rule was applied to.
    """

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
    utme_scores: tuple[UtmeSubjectScoreView, ...]
    utme_aggregate: int

    @classmethod
    def of(cls, applicant: Applicant) -> "ApplicantView":
        """Project an applicant. The only place in this context that reads one field by field."""
        return cls(
            applicant_id=applicant.applicant_id,
            applied_program_id=applicant.applied_program_id,
            offered_program_id=applicant.offered_program_id,
            session_id=applicant.session_id,
            status=applicant.status.value,
            is_fee_cleared=applicant.is_fee_cleared,
            is_final=applicant.is_final,
            full_name=applicant.bio_data.full_name,
            date_of_birth=applicant.bio_data.date_of_birth,
            email=applicant.bio_data.email,
            phone_number=applicant.bio_data.phone_number,
            utme_scores=tuple(
                UtmeSubjectScoreView(subject=score.subject, score=score.score)
                for score in applicant.utme_result.scores
            ),
            utme_aggregate=applicant.utme_result.aggregate,
        )


@dataclass(frozen=True)
class AdmissionCycleView:
    """One program's intake for one session, and how much of it is left.

    ``places_remaining`` and ``is_full`` are derived by the aggregate rather than subtracted
    here, so the numbers reported are the ones the quota invariant is actually enforced on.
    A registrar reading a dashboard and the cycle refusing an offer must never disagree.
    """

    program_id: str
    session_id: str
    quota: int
    offers_made: int
    places_remaining: int
    is_full: bool

    @classmethod
    def of(cls, cycle: AdmissionCycle) -> "AdmissionCycleView":
        return cls(
            program_id=cycle.program_id,
            session_id=cycle.session_id,
            quota=cycle.quota,
            offers_made=cycle.offers_made,
            places_remaining=cycle.places_remaining,
            is_full=cycle.is_full,
        )


@dataclass(frozen=True)
class ProgramEntryRequirementView:
    """What a program demands of an applicant's subjects, for one session.

    Both ``required_subjects`` and each of ``one_of_groups`` are sorted. The aggregate holds
    them as frozensets, which have no order, so an unsorted projection would give a different
    response body on every process — the kind of instability that makes an API impossible to
    cache or to diff. Neither set means anything by its order, so imposing one costs nothing.

    ``one_of_groups`` keeps its own tuple order, which the aggregate does define.
    """

    program_id: str
    session_id: str
    required_subjects: tuple[str, ...]
    one_of_groups: tuple[tuple[str, ...], ...]

    @classmethod
    def of(cls, requirement: ProgramEntryRequirement) -> "ProgramEntryRequirementView":
        return cls(
            program_id=requirement.program_id,
            session_id=requirement.session_id,
            required_subjects=tuple(sorted(requirement.required_subjects)),
            one_of_groups=tuple(
                tuple(sorted(group.options)) for group in requirement.one_of_groups
            ),
        )


@dataclass(frozen=True)
class AlternativeProgramPolicyView:
    """Where a program overflows to, in preference order.

    ``alternatives`` keeps the tuple's order untouched: order is the whole content of this
    policy, and a projection that sorted it would report a different admissions policy from
    the one the offer flow will actually walk.
    """

    program_id: str
    session_id: str
    alternatives: tuple[str, ...]

    @classmethod
    def of(cls, policy: AlternativeProgramPolicy) -> "AlternativeProgramPolicyView":
        return cls(
            program_id=policy.program_id,
            session_id=policy.session_id,
            alternatives=policy.alternatives,
        )
