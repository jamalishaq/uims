"""Screening as an outcome: the university says no far more often than it says yes.

The assertion this file exists for is the one that contains no ``pytest.raises``. An
applicant whose subjects do not qualify them is the commonest way an application ends, and
the use case returns that verdict as a value. If screening ever starts raising on it, the
test asserting the returned outcome is what fails, and it fails loudly rather than by
passing a ``pytest.raises`` that was never meant to be there.

The errors that *are* raised here are the two that mean the use case could not do its job
at all — an applicant nobody stored, and a program whose requirement nobody published —
plus the domain's own refusals, which pass through untranslated because the aggregate has
already said exactly what was wrong.
"""

from datetime import date

import pytest

from admissions.application import (
    ApplicantNotFoundError,
    ApplicantNotQualified,
    ApplicantQualified,
    EntryRequirementNotFoundError,
    ScreenApplicant,
    ScreenApplicantCommand,
)
from admissions.domain import (
    Applicant,
    ApplicantAlreadyScreenedError,
    ApplicationOutcomeFinalError,
    ApplicationStatus,
    BioData,
    ProgramEntryRequirement,
    SubjectGroup,
    UtmeResult,
    UtmeSubjectScore,
)
from admissions.ports import ApplicantRepositoryPort, ProgramEntryRequirementRepositoryPort

APPLICANT_ID = "app-0001"
PROGRAM_ID = "prg-csc"
SESSION_ID = "sess-2026"
OTHER_SESSION_ID = "sess-2027"

BIO = BioData("Adaeze Okonkwo", date_of_birth=date(2006, 4, 1), email="adaeze@example.com")

QUALIFYING_SUBJECTS = ("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", "CHEMISTRY")
UNQUALIFYING_SUBJECTS = ("USE OF ENGLISH", "LITERATURE IN ENGLISH", "GOVERNMENT", "CRS")


def a_utme_result(subjects: tuple[str, ...]) -> UtmeResult:
    return UtmeResult(tuple(UtmeSubjectScore(subject, 70) for subject in subjects))


def an_applicant(subjects: tuple[str, ...] = QUALIFYING_SUBJECTS) -> Applicant:
    return Applicant.apply(
        applicant_id=APPLICANT_ID,
        applied_program_id=PROGRAM_ID,
        session_id=SESSION_ID,
        bio_data=BIO,
        utme_result=a_utme_result(subjects),
    )


def a_computer_science_requirement(session_id: str = SESSION_ID) -> ProgramEntryRequirement:
    """LASU-style: three required subjects and a choice for the fourth."""
    return ProgramEntryRequirement.for_program(
        PROGRAM_ID,
        session_id,
        required_subjects=("USE OF ENGLISH", "MATHEMATICS", "PHYSICS"),
        one_of_groups=(SubjectGroup(frozenset({"CHEMISTRY", "BIOLOGY", "GEOGRAPHY"})),),
    )


@pytest.fixture
async def requirement_published(requirements: ProgramEntryRequirementRepositoryPort) -> None:
    await requirements.add(a_computer_science_requirement())


@pytest.mark.usefixtures("requirement_published")
class TestScreeningAQualifiedApplicant:
    async def test_the_outcome_says_they_qualified(
        self, screen_applicant: ScreenApplicant, applicants: ApplicantRepositoryPort
    ) -> None:
        await applicants.add(an_applicant())

        outcome = await screen_applicant.execute(ScreenApplicantCommand(APPLICANT_ID))

        assert outcome == ApplicantQualified(applicant_id=APPLICANT_ID, program_id=PROGRAM_ID)

    async def test_they_are_left_screened_and_waiting_for_an_offer_decision(
        self, screen_applicant: ScreenApplicant, applicants: ApplicantRepositoryPort
    ) -> None:
        """Whether a place exists is ``AdmissionCycle``'s question, asked by another use case."""
        await applicants.add(an_applicant())

        await screen_applicant.execute(ScreenApplicantCommand(APPLICANT_ID))

        stored = await applicants.get(APPLICANT_ID)
        assert stored is not None
        assert stored.status is ApplicationStatus.SCREENED
        assert stored.offered_program_id is None


@pytest.mark.usefixtures("requirement_published")
class TestScreeningAnUnqualifiedApplicant:
    async def test_the_verdict_is_returned_rather_than_raised(
        self, screen_applicant: ScreenApplicant, applicants: ApplicantRepositoryPort
    ) -> None:
        """No ``pytest.raises`` anywhere in this test, on purpose: this is a normal outcome."""
        await applicants.add(an_applicant(UNQUALIFYING_SUBJECTS))

        outcome = await screen_applicant.execute(ScreenApplicantCommand(APPLICANT_ID))

        assert isinstance(outcome, ApplicantNotQualified)
        assert outcome.applicant_id == APPLICANT_ID
        assert outcome.program_id == PROGRAM_ID

    async def test_the_outcome_says_which_demands_went_unmet(
        self, screen_applicant: ScreenApplicant, applicants: ApplicantRepositoryPort
    ) -> None:
        """So a rejection letter can say what was missing, not merely that something was."""
        await applicants.add(an_applicant(UNQUALIFYING_SUBJECTS))

        outcome = await screen_applicant.execute(ScreenApplicantCommand(APPLICANT_ID))

        assert isinstance(outcome, ApplicantNotQualified)
        assert outcome.unmet == (
            "MATHEMATICS",
            "PHYSICS",
            "one of {BIOLOGY, CHEMISTRY, GEOGRAPHY}",
        )

    async def test_the_application_is_closed_with_no_offer_available(
        self, screen_applicant: ScreenApplicant, applicants: ApplicantRepositoryPort
    ) -> None:
        """Terminal, and not a failure state: there is nothing left to decide about them."""
        await applicants.add(an_applicant(UNQUALIFYING_SUBJECTS))

        await screen_applicant.execute(ScreenApplicantCommand(APPLICANT_ID))

        stored = await applicants.get(APPLICANT_ID)
        assert stored is not None
        assert stored.status is ApplicationStatus.NO_OFFER_AVAILABLE
        assert stored.is_final is True


class TestScreeningWhatCannotBeScreened:
    async def test_an_unknown_applicant_is_an_error(
        self, screen_applicant: ScreenApplicant, requirements: ProgramEntryRequirementRepositoryPort
    ) -> None:
        await requirements.add(a_computer_science_requirement())

        with pytest.raises(ApplicantNotFoundError):
            await screen_applicant.execute(ScreenApplicantCommand("app-nobody"))

    async def test_a_program_with_no_published_requirement_is_an_error(
        self, screen_applicant: ScreenApplicant, applicants: ApplicantRepositoryPort
    ) -> None:
        """Screening against a rule nobody wrote would turn a whole cohort away silently."""
        await applicants.add(an_applicant())

        with pytest.raises(EntryRequirementNotFoundError):
            await screen_applicant.execute(ScreenApplicantCommand(APPLICANT_ID))

        stored = await applicants.get(APPLICANT_ID)
        assert stored is not None
        assert stored.status is ApplicationStatus.APPLIED

    async def test_the_requirement_is_looked_up_for_the_applicants_own_session(
        self,
        screen_applicant: ScreenApplicant,
        applicants: ApplicantRepositoryPort,
        requirements: ProgramEntryRequirementRepositoryPort,
    ) -> None:
        """Entry requirements are session-scoped; next year's does not screen this year's."""
        await applicants.add(an_applicant())
        await requirements.add(a_computer_science_requirement(OTHER_SESSION_ID))

        with pytest.raises(EntryRequirementNotFoundError):
            await screen_applicant.execute(ScreenApplicantCommand(APPLICANT_ID))

    @pytest.mark.usefixtures("requirement_published")
    async def test_screening_twice_is_the_domains_refusal_and_passes_through(
        self, screen_applicant: ScreenApplicant, applicants: ApplicantRepositoryPort
    ) -> None:
        await applicants.add(an_applicant())
        await screen_applicant.execute(ScreenApplicantCommand(APPLICANT_ID))

        with pytest.raises(ApplicantAlreadyScreenedError):
            await screen_applicant.execute(ScreenApplicantCommand(APPLICANT_ID))

        stored = await applicants.get(APPLICANT_ID)
        assert stored is not None
        assert stored.status is ApplicationStatus.SCREENED

    @pytest.mark.usefixtures("requirement_published")
    async def test_an_application_that_already_ended_cannot_be_screened(
        self, screen_applicant: ScreenApplicant, applicants: ApplicantRepositoryPort
    ) -> None:
        applicant = an_applicant(UNQUALIFYING_SUBJECTS)
        await applicants.add(applicant)
        await screen_applicant.execute(ScreenApplicantCommand(APPLICANT_ID))

        with pytest.raises(ApplicationOutcomeFinalError):
            await screen_applicant.execute(ScreenApplicantCommand(APPLICANT_ID))

        stored = await applicants.get(APPLICANT_ID)
        assert stored is not None
        assert stored.status is ApplicationStatus.NO_OFFER_AVAILABLE
