"""Screen one applicant against the entry requirement of the program they applied for."""

from dataclasses import dataclass

from admissions.application.errors import ApplicantNotFoundError, EntryRequirementNotFoundError
from admissions.domain.subject_combination_rule import SubjectCombinationRule
from admissions.ports.applicant_repository import ApplicantRepositoryPort
from admissions.ports.entry_requirement_repository import ProgramEntryRequirementRepositoryPort


@dataclass(frozen=True)
class ScreenApplicantCommand:
    """An identifier only: the use case loads the application and the rule itself."""

    applicant_id: str


@dataclass(frozen=True)
class ApplicantQualified:
    """The applicant's subjects meet the program's requirement. No offer has been made."""

    applicant_id: str
    program_id: str


@dataclass(frozen=True)
class ApplicantNotQualified:
    """The applicant's subjects do not meet it, and the application is closed.

    ``unmet`` names each demand that went unsatisfied, in the requirement's own words, so
    a letter or a screen can tell the applicant what was missing rather than only that
    something was.
    """

    applicant_id: str
    program_id: str
    unmet: tuple[str, ...]


ScreeningOutcome = ApplicantQualified | ApplicantNotQualified
"""Both ways screening can end. Neither is an exception; callers handle both."""


class ScreenApplicant:
    """Record that an applicant was screened, and what screening found.

    The verdict is returned, not raised, and that is the whole point of this use case.
    Most people who apply to a Nigerian university are not offered a place, and an
    unqualified combination is the commonest way an application ends — orchestrating that
    through an exception would put the ordinary path on the error path and would let a
    caller that forgot a ``try`` treat "we said no" as "we crashed".

    Screening does not offer anybody anything. Whether a qualified applicant actually gets
    a place depends on whether the program's ``AdmissionCycle`` has one left, which is
    ``MakeOfferToApplicant``'s question to ask. This use case leaves a qualified applicant
    ``SCREENED`` and waiting for it.
    """

    def __init__(
        self,
        applicants: ApplicantRepositoryPort,
        requirements: ProgramEntryRequirementRepositoryPort,
        rule: SubjectCombinationRule | None = None,
    ) -> None:
        self._applicants = applicants
        self._requirements = requirements
        self._rule = rule or SubjectCombinationRule()

    async def execute(self, command: ScreenApplicantCommand) -> ScreeningOutcome:
        """Screen the applicant and return what was found.

        An applicant who does not qualify is closed off here with ``record_no_offer()``
        rather than left screened and pending: there is nothing further to decide about
        them, and leaving them in play would invite the offer flow to consider somebody
        screening already ruled out.

        Returns:
            ApplicantQualified: the subjects meet the requirement; the applicant is
                screened and awaits an offer decision.
            ApplicantNotQualified: they do not; the application is now
                ``NO_OFFER_AVAILABLE``.

        Raises:
            ApplicantNotFoundError: no application is stored under that id.
            EntryRequirementNotFoundError: the program has no requirement this session.
            ApplicantAlreadyScreenedError: the applicant has already been screened.
            ApplicationOutcomeFinalError: the application already reached an outcome.
        """
        applicant = await self._applicants.get(command.applicant_id)
        if applicant is None:
            raise ApplicantNotFoundError(f"no applicant stored with id {command.applicant_id!r}")

        requirement = await self._requirements.get(
            applicant.applied_program_id, applicant.session_id
        )
        if requirement is None:
            raise EntryRequirementNotFoundError(
                f"no entry requirement published for program "
                f"{applicant.applied_program_id!r} in session {applicant.session_id!r}"
            )

        # Screening happened, whatever it found. The domain rejects a second screening and
        # a screening of a closed application, and those errors are the domain's to state.
        applicant.screen()

        unmet = self._rule.unmet(requirement, applicant.utme_result)
        if unmet:
            applicant.record_no_offer()
            await self._applicants.save(applicant)
            return ApplicantNotQualified(
                applicant_id=applicant.applicant_id,
                program_id=applicant.applied_program_id,
                unmet=unmet,
            )

        await self._applicants.save(applicant)
        return ApplicantQualified(
            applicant_id=applicant.applicant_id,
            program_id=applicant.applied_program_id,
        )
