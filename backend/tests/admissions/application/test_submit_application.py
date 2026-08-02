"""Application submission: the one moment the program on the form is checked at all.

Programs belong to Faculty & Department, and this is where Admissions asks about one — at
application time, and only then. The tests that matter most are the two refusals, because
they are different refusals wearing similar clothes: a program nobody recognises is a bad
id on a form, and a program that exists but is closed is a real program not taking
applicants. Collapsing them would leave an applicant unable to tell a typo from a
deadline they missed.

Neither refusal is an outcome. Nothing about the applicant has been assessed at this point
— they have not been screened, nobody has looked at their subjects — so there is no
university decision here to return as a value, only a form that could not be accepted.
"""

from datetime import date

import pytest

from admissions.adapters.outbound import InMemoryProgramInfoAdapter
from admissions.application import (
    ProgramNotAdmittingError,
    ProgramNotFoundError,
    SubmitApplication,
    SubmitApplicationCommand,
)
from admissions.domain import (
    ApplicationStatus,
    InvalidBioDataError,
    InvalidUtmeResultError,
    InvalidUtmeScoreError,
    MissingIdentifierError,
)
from admissions.ports import ApplicantRepositoryPort, DuplicateAggregateError

APPLICANT_ID = "app-0001"
PROGRAM_ID = "prg-csc"
SESSION_ID = "sess-2026"
OTHER_SESSION_ID = "sess-2027"

UTME_SCORES = (
    ("USE OF ENGLISH", 78),
    ("MATHEMATICS", 65),
    ("PHYSICS", 70),
    ("CHEMISTRY", 62),
)


def a_command(**overrides: object) -> SubmitApplicationCommand:
    fields: dict[str, object] = {
        "applicant_id": APPLICANT_ID,
        "program_id": PROGRAM_ID,
        "session_id": SESSION_ID,
        "full_name": "Adaeze Okonkwo",
        "utme_scores": UTME_SCORES,
        "date_of_birth": date(2006, 4, 1),
        "email": "adaeze@example.com",
    }
    fields.update(overrides)
    return SubmitApplicationCommand(**fields)  # type: ignore[arg-type]


@pytest.fixture
def program_admitting(programs: InMemoryProgramInfoAdapter) -> None:
    programs.register(PROGRAM_ID, SESSION_ID, admitting=True)


@pytest.mark.usefixtures("program_admitting")
class TestSubmittingToAnOpenProgram:
    def test_the_application_starts_with_nothing_decided(
        self, submit_application: SubmitApplication
    ) -> None:
        applicant = submit_application.execute(a_command())

        assert applicant.status is ApplicationStatus.APPLIED
        assert applicant.offered_program_id is None
        assert applicant.is_fee_cleared is False

    def test_the_program_applied_for_is_the_one_on_the_form(
        self, submit_application: SubmitApplication
    ) -> None:
        applicant = submit_application.execute(a_command())

        assert applicant.applied_program_id == PROGRAM_ID
        assert applicant.session_id == SESSION_ID

    def test_the_form_becomes_value_objects_the_domain_owns(
        self, submit_application: SubmitApplication
    ) -> None:
        """Primitives in, aggregate out: the caller never constructs a ``UtmeResult``."""
        applicant = submit_application.execute(a_command())

        assert applicant.bio_data.full_name == "Adaeze Okonkwo"
        assert applicant.utme_result.aggregate == 275
        assert applicant.utme_result.score_for("PHYSICS") == 70

    def test_the_application_is_stored(
        self, submit_application: SubmitApplication, applicants: ApplicantRepositoryPort
    ) -> None:
        applicant = submit_application.execute(a_command())

        assert applicants.get(APPLICANT_ID) is applicant

    def test_a_second_application_under_the_same_id_is_refused(
        self, submit_application: SubmitApplication
    ) -> None:
        submit_application.execute(a_command())

        with pytest.raises(DuplicateAggregateError):
            submit_application.execute(a_command())


class TestSubmittingToAProgramThatWillNotTakeIt:
    def test_a_program_faculty_and_department_does_not_know_is_refused(
        self, submit_application: SubmitApplication
    ) -> None:
        with pytest.raises(ProgramNotFoundError):
            submit_application.execute(a_command())

    def test_a_program_that_exists_but_is_closed_is_a_different_refusal(
        self, submit_application: SubmitApplication, programs: InMemoryProgramInfoAdapter
    ) -> None:
        """A typo and a missed deadline are not the same thing to say to an applicant."""
        programs.register(PROGRAM_ID, SESSION_ID, admitting=False)

        with pytest.raises(ProgramNotAdmittingError):
            submit_application.execute(a_command())

    @pytest.mark.parametrize(
        "admitting",
        [pytest.param(True, id="admitting"), pytest.param(False, id="closed")],
    )
    def test_nothing_is_stored_when_the_program_is_wrong(
        self,
        submit_application: SubmitApplication,
        applicants: ApplicantRepositoryPort,
        programs: InMemoryProgramInfoAdapter,
        admitting: bool,
    ) -> None:
        programs.register(PROGRAM_ID, OTHER_SESSION_ID, admitting=admitting)

        with pytest.raises((ProgramNotFoundError, ProgramNotAdmittingError)):
            submit_application.execute(a_command())

        assert applicants.get(APPLICANT_ID) is None

    def test_the_program_is_checked_for_the_session_applied_for(
        self, submit_application: SubmitApplication, programs: InMemoryProgramInfoAdapter
    ) -> None:
        """Admitting next year is not admitting this year."""
        programs.register(PROGRAM_ID, OTHER_SESSION_ID, admitting=True)

        with pytest.raises(ProgramNotFoundError):
            submit_application.execute(a_command())


class TestAFormThatCouldNotBeAnApplication:
    """The domain's refusals, raised before Faculty & Department is troubled at all."""

    def test_a_result_with_the_wrong_number_of_subjects_is_refused(
        self, submit_application: SubmitApplication
    ) -> None:
        with pytest.raises(InvalidUtmeResultError):
            submit_application.execute(a_command(utme_scores=UTME_SCORES[:3]))

    def test_a_repeated_subject_is_refused(self, submit_application: SubmitApplication) -> None:
        with pytest.raises(InvalidUtmeResultError):
            submit_application.execute(a_command(utme_scores=(*UTME_SCORES[:3], ("PHYSICS", 55))))

    def test_a_score_outside_the_permitted_range_is_refused(
        self, submit_application: SubmitApplication
    ) -> None:
        with pytest.raises(InvalidUtmeScoreError):
            submit_application.execute(
                a_command(utme_scores=(*UTME_SCORES[:3], ("CHEMISTRY", 101)))
            )

    def test_a_blank_name_is_refused(self, submit_application: SubmitApplication) -> None:
        with pytest.raises(MissingIdentifierError):
            submit_application.execute(a_command(full_name="   "))

    def test_a_date_of_birth_in_the_future_is_refused(
        self, submit_application: SubmitApplication
    ) -> None:
        with pytest.raises(InvalidBioDataError):
            submit_application.execute(a_command(date_of_birth=date(2999, 1, 1)))

    def test_a_blank_applicant_id_is_refused(
        self, submit_application: SubmitApplication, programs: InMemoryProgramInfoAdapter
    ) -> None:
        programs.register(PROGRAM_ID, SESSION_ID, admitting=True)

        with pytest.raises(MissingIdentifierError):
            submit_application.execute(a_command(applicant_id=""))

    def test_a_malformed_form_is_refused_without_asking_about_the_program(
        self, submit_application: SubmitApplication, applicants: ApplicantRepositoryPort
    ) -> None:
        """No program was ever registered here: the local judgement runs first, and is enough."""
        with pytest.raises(InvalidUtmeResultError):
            submit_application.execute(a_command(utme_scores=()))

        assert applicants.get(APPLICANT_ID) is None
