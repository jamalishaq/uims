"""Submit one application, once the program named on it has been confirmed real and open."""

from dataclasses import dataclass
from datetime import date

from admissions.application.errors import ProgramNotAdmittingError, ProgramNotFoundError
from admissions.domain.applicant import Applicant
from admissions.domain.values import BioData, UtmeResult, UtmeSubjectScore
from admissions.ports.applicant_repository import ApplicantRepositoryPort
from admissions.ports.program_info import ProgramInfoPort


@dataclass(frozen=True)
class SubmitApplicationCommand:
    """One filled-in application form, in primitives.

    Primitives and not value objects, for the reason ``RegisterNewStudentCommand`` is: a
    caller at the edge — an HTTP handler, a JAMB import — holds strings and numbers, and
    making it construct a ``UtmeResult`` first would put the domain's validation outside
    the use case that is supposed to run it. ``utme_scores`` is a tuple of
    ``(subject, score)`` pairs, and whether four of them are a legal result is
    ``UtmeResult``'s judgement, made below.
    """

    applicant_id: str
    program_id: str
    session_id: str
    full_name: str
    utme_scores: tuple[tuple[str, int], ...]
    date_of_birth: date | None = None
    email: str | None = None
    phone_number: str | None = None


class SubmitApplication:
    """Turn a filled-in form into an ``Applicant``, or refuse it.

    The one thing this use case knows that the domain cannot is whether the program exists
    and is admitting. Programs belong to Faculty & Department (CLAUDE.md section 3), so
    that fact is pulled through ``ProgramInfoPort`` at application time — the only moment
    it is worth asking, because a program closing later must not retroactively unmake
    applications already accepted under it.

    Nothing is decided about the applicant here. They are ``APPLIED``, holding no offer,
    waiting for ``ScreenApplicant`` to judge their subjects and ``MakeOfferToApplicant`` to
    find them a place. Both refusals this use case can make are about the form, not the
    person.
    """

    def __init__(self, applicants: ApplicantRepositoryPort, programs: ProgramInfoPort) -> None:
        self._applicants = applicants
        self._programs = programs

    def execute(self, command: SubmitApplicationCommand) -> Applicant:
        """Store and return the new application.

        Returns:
            Applicant: ``APPLIED``, with no offered program and no fee cleared.

        Raises:
            ProgramNotFoundError: Faculty & Department does not know that program.
            ProgramNotAdmittingError: it exists but is closed for that session.
            DuplicateAggregateError: an application is already stored under that id.
            AdmissionsError: the bio-data, the UTME result or an identifier is invalid.
                Domain errors pass through untranslated — the domain already says exactly
                what went wrong.
        """
        # The form is checked before the port is asked. A malformed UTME result is wrong
        # whatever Faculty & Department would have said, and failing on it here keeps the
        # cheap local judgement ahead of the cross-context round trip.
        bio_data = BioData(
            full_name=command.full_name,
            date_of_birth=command.date_of_birth,
            email=command.email,
            phone_number=command.phone_number,
        )
        utme_result = UtmeResult(
            tuple(UtmeSubjectScore(subject, score) for subject, score in command.utme_scores)
        )

        program = self._programs.program_for(command.program_id, command.session_id)
        if program is None:
            raise ProgramNotFoundError(
                f"no program is known with id {command.program_id!r} "
                f"in session {command.session_id!r}"
            )
        if not program.is_admitting:
            raise ProgramNotAdmittingError(
                f"program {command.program_id!r} is not admitting in session {command.session_id!r}"
            )

        applicant = Applicant.apply(
            applicant_id=command.applicant_id,
            applied_program_id=command.program_id,
            session_id=command.session_id,
            bio_data=bio_data,
            utme_result=utme_result,
        )
        self._applicants.add(applicant)
        return applicant
