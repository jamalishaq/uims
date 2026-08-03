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

from admissions.domain.applicant import Applicant


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
