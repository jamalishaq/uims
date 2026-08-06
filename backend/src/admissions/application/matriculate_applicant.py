"""Turn an accepted, fee-cleared applicant into a student.

The last thing that happens to an application, and the second of the two facts this context
publishes. Student Profile creates the student on it; nothing is published back, because a
matric number is not needed at acceptance-letter time and issuing one is not this context's
job (CLAUDE.md section 3).

**Human-triggered, never automatic on payment.** CLAUDE.md section 4 lists that among the
things not to undo: the acceptance fee clearing sets a flag, and a person decides when to
act on it. The flag and the transition are two methods on the aggregate precisely so that
nothing can quietly do both. In the role model this is the departmental registrar's one
per-applicant act.

Only the acceptance fee gates this. An outstanding matriculation fee does not, and that is
also section 4's instruction rather than an oversight here.
"""

from dataclasses import dataclass

from admissions.application.errors import ApplicantNotFoundError
from admissions.domain.events import StudentMatriculated
from admissions.ports.applicant_repository import ApplicantRepositoryPort
from admissions.ports.event_publisher import EventPublisherPort


@dataclass(frozen=True)
class MatriculateApplicantCommand:
    """An identifier only. Everything the transition checks is already on the aggregate."""

    applicant_id: str


@dataclass(frozen=True)
class ApplicantMatriculated:
    """The applicant is now a student somewhere else in the system.

    No matric number and no student id, because neither exists yet as far as this context is
    concerned — both are minted by Student Profile from the event, and asking for them back
    would be this context taking an interest in another's identifiers.
    """

    applicant_id: str
    program_id: str
    session_id: str


class MatriculateApplicant:
    """Matriculate an applicant who accepted and whose acceptance fee has cleared."""

    def __init__(
        self,
        applicants: ApplicantRepositoryPort,
        events: EventPublisherPort,
    ) -> None:
        self._applicants = applicants
        self._events = events

    async def execute(self, command: MatriculateApplicantCommand) -> ApplicantMatriculated:
        """Matriculate, publish the fact, then store the applicant.

        Published before saved, for ``AcceptOffer``'s reason and with the same healing
        property: ``StudentMatriculatedHandler`` looks the applicant up before registering
        anybody, so a crash after publishing leaves a student created against an applicant
        still stored as ``ACCEPTED``, and retrying matriculation is a no-op on that side and
        completes this one. The other order would strand an applicant who is matriculated and
        is nobody's student, with ``matriculate()`` refusing to be run again to fix it.

        Returns:
            ApplicantMatriculated: the application is closed and a student exists.

        Raises:
            ApplicantNotFoundError: no application is stored under that id.
            OfferNotAcceptedError: the applicant has not accepted an offer.
            AcceptanceFeeNotClearedError: the gating acceptance fee has not cleared.
            ApplicationOutcomeFinalError: the application already reached an outcome.
        """
        applicant = await self._applicants.get(command.applicant_id)
        if applicant is None:
            raise ApplicantNotFoundError(f"no applicant stored with id {command.applicant_id!r}")

        applicant.matriculate()

        # Present for ``AcceptOffer``'s reason: matriculation requires an accepted offer, and
        # an accepted offer requires a program it was made on.
        program_id = applicant.offered_program_id
        await self._events.publish(
            StudentMatriculated(
                applicant_id=applicant.applicant_id,
                program_id=program_id,
                session_id=applicant.session_id,
                bio_data=applicant.bio_data,
            )
        )
        await self._applicants.save(applicant)

        return ApplicantMatriculated(
            applicant_id=applicant.applicant_id,
            program_id=program_id,
            session_id=applicant.session_id,
        )
