"""The admissions state machine: every transition an applicant can make, and every one they cannot.

The point of this file is the illegal half. An aggregate that only refuses the
transitions someone remembered to test is an aggregate that will one day matriculate a
person who declined their offer, because a use case forgot a check the domain never
enforced. So each legal edge is asserted once, and the terminal outcomes are asserted
exhaustively against every mutator rather than sampled.

Zero infrastructure: no repository, no ports, no fixtures beyond builders.
"""

from collections.abc import Callable
from datetime import date
from functools import partial

import pytest

from admissions.domain import (
    AcceptanceFeeNotClearedError,
    Applicant,
    ApplicantAlreadyScreenedError,
    ApplicantNotScreenedError,
    ApplicationOutcomeFinalError,
    ApplicationStatus,
    BioData,
    InvalidBioDataError,
    InvalidUtmeResultError,
    MissingIdentifierError,
    NoOfferToRespondToError,
    OfferAlreadyMadeError,
    OfferAlreadyRespondedToError,
    OfferNotAcceptedError,
    UtmeResult,
    UtmeSubjectScore,
)

APPLICANT_ID = "app-0001"
APPLIED_PROGRAM_ID = "prg-csc"
ALTERNATIVE_PROGRAM_ID = "prg-maths"
SESSION_ID = "sess-2026"

BIO = BioData("Adaeze Okonkwo", date_of_birth=date(2006, 4, 1), email="adaeze@example.com")
UTME = UtmeResult(
    (
        UtmeSubjectScore("USE OF ENGLISH", 78),
        UtmeSubjectScore("MATHEMATICS", 65),
        UtmeSubjectScore("PHYSICS", 70),
        UtmeSubjectScore("CHEMISTRY", 62),
    )
)


def an_applicant(**overrides: object) -> Applicant:
    fields: dict[str, object] = {
        "applicant_id": APPLICANT_ID,
        "applied_program_id": APPLIED_PROGRAM_ID,
        "session_id": SESSION_ID,
        "bio_data": BIO,
        "utme_result": UTME,
    }
    fields.update(overrides)
    return Applicant.apply(**fields)  # type: ignore[arg-type]


def a_screened_applicant() -> Applicant:
    applicant = an_applicant()
    applicant.screen()
    return applicant


def an_offered_applicant(program_id: str = APPLIED_PROGRAM_ID) -> Applicant:
    applicant = a_screened_applicant()
    applicant.offer(program_id)
    return applicant


def an_accepted_applicant() -> Applicant:
    applicant = an_offered_applicant()
    applicant.accept()
    return applicant


def a_fee_cleared_applicant() -> Applicant:
    applicant = an_accepted_applicant()
    applicant.record_acceptance_fee_paid()
    return applicant


def a_matriculated_applicant() -> Applicant:
    applicant = a_fee_cleared_applicant()
    applicant.matriculate()
    return applicant


def a_declined_applicant() -> Applicant:
    applicant = an_offered_applicant()
    applicant.decline()
    return applicant


def a_no_offer_applicant() -> Applicant:
    applicant = a_screened_applicant()
    applicant.record_no_offer()
    return applicant


Mutator = Callable[[Applicant], None]

EVERY_MUTATOR_BUT_FEE = [
    pytest.param(Applicant.screen, id="screen"),
    pytest.param(partial(Applicant.offer, program_id=ALTERNATIVE_PROGRAM_ID), id="offer"),
    pytest.param(Applicant.record_no_offer, id="record_no_offer"),
    pytest.param(Applicant.accept, id="accept"),
    pytest.param(Applicant.decline, id="decline"),
    pytest.param(Applicant.matriculate, id="matriculate"),
]

TERMINAL_APPLICANTS = [
    pytest.param(a_declined_applicant, ApplicationStatus.DECLINED, id="declined"),
    pytest.param(a_no_offer_applicant, ApplicationStatus.NO_OFFER_AVAILABLE, id="no_offer"),
    pytest.param(a_matriculated_applicant, ApplicationStatus.MATRICULATED, id="matriculated"),
]


class TestApplication:
    def test_a_new_application_has_been_decided_in_no_way_at_all(self) -> None:
        applicant = an_applicant()

        assert applicant.status is ApplicationStatus.APPLIED
        assert applicant.applied_program_id == APPLIED_PROGRAM_ID
        assert applicant.offered_program_id is None
        assert applicant.is_fee_cleared is False
        assert applicant.is_final is False

    def test_an_application_carries_the_bio_data_and_utme_result_it_was_made_with(self) -> None:
        applicant = an_applicant()

        assert applicant.bio_data == BIO
        assert applicant.utme_result == UTME
        assert applicant.session_id == SESSION_ID

    @pytest.mark.parametrize("field", ["applicant_id", "applied_program_id", "session_id"])
    @pytest.mark.parametrize("blank", ["", "   "])
    def test_a_blank_identifier_is_rejected(self, field: str, blank: str) -> None:
        with pytest.raises(MissingIdentifierError):
            an_applicant(**{field: blank})

    def test_bio_data_must_be_bio_data(self) -> None:
        with pytest.raises(InvalidBioDataError):
            an_applicant(bio_data="Adaeze Okonkwo")

    def test_a_utme_result_must_be_a_utme_result(self) -> None:
        with pytest.raises(InvalidUtmeResultError):
            an_applicant(utme_result=275)


class TestScreening:
    def test_an_application_is_screened_once_it_has_been_applied_for(self) -> None:
        applicant = an_applicant()

        applicant.screen()

        assert applicant.status is ApplicationStatus.SCREENED

    def test_screening_cannot_be_performed_twice(self) -> None:
        applicant = a_screened_applicant()

        with pytest.raises(ApplicantAlreadyScreenedError):
            applicant.screen()

        assert applicant.status is ApplicationStatus.SCREENED

    @pytest.mark.parametrize(
        ("build", "status"),
        [
            pytest.param(an_offered_applicant, ApplicationStatus.OFFERED, id="offered"),
            pytest.param(an_accepted_applicant, ApplicationStatus.ACCEPTED, id="accepted"),
        ],
    )
    def test_an_applicant_past_screening_cannot_be_screened_again(
        self, build: Callable[[], Applicant], status: ApplicationStatus
    ) -> None:
        applicant = build()

        with pytest.raises(ApplicantAlreadyScreenedError):
            applicant.screen()

        assert applicant.status is status


class TestOffer:
    def test_a_screened_applicant_can_be_offered_the_program_they_applied_for(self) -> None:
        applicant = a_screened_applicant()

        applicant.offer(APPLIED_PROGRAM_ID)

        assert applicant.status is ApplicationStatus.OFFERED
        assert applicant.offered_program_id == APPLIED_PROGRAM_ID

    def test_the_offered_program_may_differ_from_the_applied_one(self) -> None:
        """An alternative offer. What they asked for is not overwritten by what they got."""
        applicant = a_screened_applicant()

        applicant.offer(ALTERNATIVE_PROGRAM_ID)

        assert applicant.offered_program_id == ALTERNATIVE_PROGRAM_ID
        assert applicant.applied_program_id == APPLIED_PROGRAM_ID

    def test_an_unscreened_applicant_cannot_be_offered_a_place(self) -> None:
        applicant = an_applicant()

        with pytest.raises(ApplicantNotScreenedError):
            applicant.offer(APPLIED_PROGRAM_ID)

        assert applicant.status is ApplicationStatus.APPLIED
        assert applicant.offered_program_id is None

    def test_an_offer_cannot_be_made_twice(self) -> None:
        applicant = an_offered_applicant(APPLIED_PROGRAM_ID)

        with pytest.raises(OfferAlreadyMadeError):
            applicant.offer(ALTERNATIVE_PROGRAM_ID)

        assert applicant.offered_program_id == APPLIED_PROGRAM_ID

    def test_an_accepted_offer_cannot_be_replaced_by_another(self) -> None:
        applicant = an_accepted_applicant()

        with pytest.raises(OfferAlreadyMadeError):
            applicant.offer(ALTERNATIVE_PROGRAM_ID)

        assert applicant.offered_program_id == APPLIED_PROGRAM_ID

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_an_offer_must_name_a_program(self, blank: str) -> None:
        applicant = a_screened_applicant()

        with pytest.raises(MissingIdentifierError):
            applicant.offer(blank)

        assert applicant.status is ApplicationStatus.SCREENED


class TestAskingBeforeOffering:
    """``require_awaiting_decision`` exists so a caller can find out *before* acting.

    ``MakeOfferToApplicant`` has to claim a place on an ``AdmissionCycle`` before it can
    offer that place to anybody, and the two aggregates are written in separate
    transactions. A place claimed for an applicant who turns out to be unscreened has no
    rollback to give it back, so the question has to be answerable in advance.
    """

    def test_a_screened_applicant_is_awaiting_a_decision(self) -> None:
        a_screened_applicant().require_awaiting_decision()

    def test_asking_changes_nothing(self) -> None:
        """A query wearing a guard's clothes: it refuses or it is silent, never both."""
        applicant = a_screened_applicant()

        applicant.require_awaiting_decision()

        assert applicant.status is ApplicationStatus.SCREENED
        assert applicant.offered_program_id is None

    def test_an_unscreened_applicant_says_so_before_a_place_is_claimed(self) -> None:
        with pytest.raises(ApplicantNotScreenedError):
            an_applicant().require_awaiting_decision()

    def test_an_applicant_already_decided_says_so(self) -> None:
        with pytest.raises(OfferAlreadyMadeError):
            an_offered_applicant().require_awaiting_decision()

    @pytest.mark.parametrize(("build", "status"), TERMINAL_APPLICANTS)
    def test_a_finished_application_says_so(
        self, build: Callable[[], Applicant], status: ApplicationStatus
    ) -> None:
        with pytest.raises(ApplicationOutcomeFinalError):
            build().require_awaiting_decision()

    def test_asking_does_not_excuse_the_aggregate_from_checking(self) -> None:
        """An aggregate that trusted callers to have asked would not be enforcing anything."""
        applicant = a_screened_applicant()
        applicant.require_awaiting_decision()
        applicant.offer(APPLIED_PROGRAM_ID)

        with pytest.raises(OfferAlreadyMadeError):
            applicant.offer(ALTERNATIVE_PROGRAM_ID)


class TestNoOfferAvailable:
    def test_a_screened_applicant_can_be_told_no_place_is_available(self) -> None:
        applicant = a_screened_applicant()

        applicant.record_no_offer()

        assert applicant.status is ApplicationStatus.NO_OFFER_AVAILABLE
        assert applicant.is_final is True
        assert applicant.offered_program_id is None

    def test_no_offer_cannot_be_recorded_before_screening(self) -> None:
        applicant = an_applicant()

        with pytest.raises(ApplicantNotScreenedError):
            applicant.record_no_offer()

        assert applicant.status is ApplicationStatus.APPLIED

    def test_no_offer_cannot_be_recorded_once_an_offer_was_made(self) -> None:
        applicant = an_offered_applicant()

        with pytest.raises(OfferAlreadyMadeError):
            applicant.record_no_offer()

        assert applicant.status is ApplicationStatus.OFFERED


class TestAcceptance:
    def test_accepting_binds_the_offered_program(self) -> None:
        applicant = an_offered_applicant(ALTERNATIVE_PROGRAM_ID)

        applicant.accept()

        assert applicant.status is ApplicationStatus.ACCEPTED
        assert applicant.offered_program_id == ALTERNATIVE_PROGRAM_ID
        assert applicant.applied_program_id == APPLIED_PROGRAM_ID
        assert applicant.is_fee_cleared is False

    @pytest.mark.parametrize(
        ("build", "status"),
        [
            pytest.param(an_applicant, ApplicationStatus.APPLIED, id="applied"),
            pytest.param(a_screened_applicant, ApplicationStatus.SCREENED, id="screened"),
        ],
    )
    def test_an_applicant_holding_no_offer_cannot_accept_one(
        self, build: Callable[[], Applicant], status: ApplicationStatus
    ) -> None:
        applicant = build()

        with pytest.raises(NoOfferToRespondToError):
            applicant.accept()

        assert applicant.status is status

    def test_an_offer_cannot_be_accepted_twice(self) -> None:
        applicant = an_accepted_applicant()

        with pytest.raises(OfferAlreadyRespondedToError):
            applicant.accept()

        assert applicant.status is ApplicationStatus.ACCEPTED


class TestDecline:
    def test_an_offer_can_be_turned_down(self) -> None:
        applicant = an_offered_applicant()

        applicant.decline()

        assert applicant.status is ApplicationStatus.DECLINED
        assert applicant.is_final is True

    @pytest.mark.parametrize(
        ("build", "status"),
        [
            pytest.param(an_applicant, ApplicationStatus.APPLIED, id="applied"),
            pytest.param(a_screened_applicant, ApplicationStatus.SCREENED, id="screened"),
        ],
    )
    def test_an_applicant_holding_no_offer_cannot_decline_one(
        self, build: Callable[[], Applicant], status: ApplicationStatus
    ) -> None:
        applicant = build()

        with pytest.raises(NoOfferToRespondToError):
            applicant.decline()

        assert applicant.status is status

    def test_an_accepted_offer_cannot_then_be_declined(self) -> None:
        applicant = an_accepted_applicant()

        with pytest.raises(OfferAlreadyRespondedToError):
            applicant.decline()

        assert applicant.status is ApplicationStatus.ACCEPTED


class TestAcceptanceFee:
    def test_clearing_the_fee_unlocks_matriculation_without_performing_it(self) -> None:
        """Paying is Billing's fact; matriculating is a registrar's act (CLAUDE.md section 4)."""
        applicant = an_accepted_applicant()

        applicant.record_acceptance_fee_paid()

        assert applicant.is_fee_cleared is True
        assert applicant.status is ApplicationStatus.ACCEPTED

    def test_a_redelivered_payment_is_a_no_op(self) -> None:
        applicant = a_fee_cleared_applicant()

        applicant.record_acceptance_fee_paid()

        assert applicant.is_fee_cleared is True
        assert applicant.status is ApplicationStatus.ACCEPTED

    def test_a_payment_redelivered_after_matriculation_is_still_a_no_op(self) -> None:
        """``AcceptanceFeePaid`` arrives at least once; a late replay is not an error."""
        applicant = a_matriculated_applicant()

        applicant.record_acceptance_fee_paid()

        assert applicant.status is ApplicationStatus.MATRICULATED

    @pytest.mark.parametrize(
        ("build", "status"),
        [
            pytest.param(an_applicant, ApplicationStatus.APPLIED, id="applied"),
            pytest.param(a_screened_applicant, ApplicationStatus.SCREENED, id="screened"),
            pytest.param(an_offered_applicant, ApplicationStatus.OFFERED, id="offered"),
        ],
    )
    def test_an_applicant_who_has_not_accepted_owes_no_acceptance_fee(
        self, build: Callable[[], Applicant], status: ApplicationStatus
    ) -> None:
        applicant = build()

        with pytest.raises(OfferNotAcceptedError):
            applicant.record_acceptance_fee_paid()

        assert applicant.is_fee_cleared is False
        assert applicant.status is status

    @pytest.mark.parametrize(
        "build",
        [
            pytest.param(a_declined_applicant, id="declined"),
            pytest.param(a_no_offer_applicant, id="no_offer"),
        ],
    )
    def test_a_payment_against_a_closed_application_is_refused(
        self, build: Callable[[], Applicant]
    ) -> None:
        applicant = build()

        with pytest.raises(ApplicationOutcomeFinalError):
            applicant.record_acceptance_fee_paid()

        assert applicant.is_fee_cleared is False


class TestMatriculation:
    def test_an_accepted_fee_cleared_applicant_matriculates(self) -> None:
        applicant = a_fee_cleared_applicant()

        applicant.matriculate()

        assert applicant.status is ApplicationStatus.MATRICULATED
        assert applicant.is_final is True
        assert applicant.offered_program_id == APPLIED_PROGRAM_ID

    def test_matriculation_without_a_cleared_acceptance_fee_fails(self) -> None:
        applicant = an_accepted_applicant()

        with pytest.raises(AcceptanceFeeNotClearedError):
            applicant.matriculate()

        assert applicant.status is ApplicationStatus.ACCEPTED

    @pytest.mark.parametrize(
        ("build", "status"),
        [
            pytest.param(an_applicant, ApplicationStatus.APPLIED, id="applied"),
            pytest.param(a_screened_applicant, ApplicationStatus.SCREENED, id="screened"),
            pytest.param(an_offered_applicant, ApplicationStatus.OFFERED, id="offered"),
        ],
    )
    def test_an_applicant_who_never_accepted_an_offer_cannot_matriculate(
        self, build: Callable[[], Applicant], status: ApplicationStatus
    ) -> None:
        applicant = build()

        with pytest.raises(OfferNotAcceptedError):
            applicant.matriculate()

        assert applicant.status is status


class TestTerminalOutcomes:
    """Declined, no-offer and matriculated are ends, not stages. Nothing moves out of them."""

    @pytest.mark.parametrize(("build", "status"), TERMINAL_APPLICANTS)
    @pytest.mark.parametrize("mutate", EVERY_MUTATOR_BUT_FEE)
    def test_no_transition_moves_an_application_out_of_a_terminal_outcome(
        self,
        build: Callable[[], Applicant],
        status: ApplicationStatus,
        mutate: Mutator,
    ) -> None:
        applicant = build()

        with pytest.raises(ApplicationOutcomeFinalError):
            mutate(applicant)

        assert applicant.status is status

    @pytest.mark.parametrize(("build", "status"), TERMINAL_APPLICANTS)
    def test_a_terminal_application_reports_itself_final(
        self, build: Callable[[], Applicant], status: ApplicationStatus
    ) -> None:
        applicant = build()

        assert applicant.is_final is True
        assert applicant.status is status
