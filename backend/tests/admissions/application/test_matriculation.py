"""The last two steps: the fee clearing, and a person deciding to act on it.

Two use cases that are deliberately *not* one. CLAUDE.md section 4 lists "do not
auto-matriculate on payment" among the decisions not to undo, and the shape of that decision
is visible here — ``RecordAcceptanceFeePaid`` sets a flag and stops, ``MatriculateApplicant``
reads the flag and refuses without it. Nothing in the system does both.

The other rule under test is that an outstanding *matriculation* fee does not gate anything.
Only the acceptance fee does, which is why the two charges Billing raises are not
interchangeable.
"""

from datetime import date

import pytest

from admissions.adapters.outbound import InMemoryEventBus
from admissions.application import (
    ApplicantNotFoundError,
    MatriculateApplicant,
    MatriculateApplicantCommand,
    RecordAcceptanceFeePaid,
    RecordAcceptanceFeePaidCommand,
)
from admissions.domain import (
    AcceptanceFeeNotClearedError,
    Applicant,
    ApplicationOutcomeFinalError,
    ApplicationStatus,
    BioData,
    OfferNotAcceptedError,
    UtmeResult,
    UtmeSubjectScore,
)
from admissions.domain.events import StudentMatriculated
from admissions.ports import ApplicantRepositoryPort

APPLICANT_ID = "app-0001"
COMPUTER_SCIENCE = "prg-csc"
MATHEMATICS = "prg-mth"
SESSION_ID = "sess-2026"

MATRICULATE = MatriculateApplicantCommand(APPLICANT_ID)
FEE_PAID = RecordAcceptanceFeePaidCommand(APPLICANT_ID)

BIO = BioData("Adaeze Okonkwo", date_of_birth=date(2006, 4, 1), email="adaeze@example.com")
SUBJECTS = ("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", "BIOLOGY")


def an_applicant(status_program: str = COMPUTER_SCIENCE) -> Applicant:
    return Applicant.apply(
        applicant_id=APPLICANT_ID,
        applied_program_id=COMPUTER_SCIENCE,
        session_id=SESSION_ID,
        bio_data=BIO,
        utme_result=UtmeResult(tuple(UtmeSubjectScore(subject, 70) for subject in SUBJECTS)),
    )


def an_accepted_applicant(program_id: str = COMPUTER_SCIENCE) -> Applicant:
    applicant = an_applicant()
    applicant.screen()
    applicant.offer(program_id)
    applicant.accept()
    return applicant


def a_cleared_applicant(program_id: str = COMPUTER_SCIENCE) -> Applicant:
    applicant = an_accepted_applicant(program_id)
    applicant.record_acceptance_fee_paid()
    return applicant


@pytest.fixture
async def accepted(applicants: ApplicantRepositoryPort) -> Applicant:
    applicant = an_accepted_applicant()
    await applicants.add(applicant)
    return applicant


@pytest.fixture
async def cleared(applicants: ApplicantRepositoryPort) -> Applicant:
    applicant = a_cleared_applicant()
    await applicants.add(applicant)
    return applicant


# ---- the fee clearing ----


class TestRecordAcceptanceFeePaid:
    async def test_it_unlocks_matriculation_without_performing_it(
        self,
        record_acceptance_fee_paid: RecordAcceptanceFeePaid,
        applicants: ApplicantRepositoryPort,
        accepted: Applicant,
    ) -> None:
        """The whole point of the two-method split: the flag moves, the status does not."""
        result = await record_acceptance_fee_paid.execute(FEE_PAID)

        stored = await applicants.get(APPLICANT_ID)
        assert stored is not None
        assert stored.is_fee_cleared is True
        assert stored.status is ApplicationStatus.ACCEPTED
        assert result.was_already_cleared is False

    async def test_a_replay_is_a_no_op_that_says_so(
        self,
        record_acceptance_fee_paid: RecordAcceptanceFeePaid,
        accepted: Applicant,
    ) -> None:
        """At-least-once delivery is normal, so a second arrival must not be an error."""
        await record_acceptance_fee_paid.execute(FEE_PAID)
        second = await record_acceptance_fee_paid.execute(FEE_PAID)

        assert second.was_already_cleared is True

    async def test_a_replay_after_matriculation_is_still_a_no_op(
        self,
        record_acceptance_fee_paid: RecordAcceptanceFeePaid,
        matriculate_applicant: MatriculateApplicant,
        cleared: Applicant,
    ) -> None:
        """The idempotency check runs before the terminal-state guard, on purpose: a late
        replay against a finished application must not raise at a handler with nothing
        useful to do with the exception."""
        await matriculate_applicant.execute(MATRICULATE)

        result = await record_acceptance_fee_paid.execute(FEE_PAID)

        assert result.was_already_cleared is True

    async def test_an_applicant_who_has_not_accepted_owes_no_acceptance_fee(
        self,
        record_acceptance_fee_paid: RecordAcceptanceFeePaid,
        applicants: ApplicantRepositoryPort,
    ) -> None:
        await applicants.add(an_applicant())
        with pytest.raises(OfferNotAcceptedError):
            await record_acceptance_fee_paid.execute(FEE_PAID)

    async def test_an_unknown_applicant_is_an_error(
        self, record_acceptance_fee_paid: RecordAcceptanceFeePaid
    ) -> None:
        with pytest.raises(ApplicantNotFoundError, match=APPLICANT_ID):
            await record_acceptance_fee_paid.execute(FEE_PAID)


# ---- matriculation ----


class TestMatriculateApplicant:
    async def test_a_cleared_applicant_matriculates_and_is_announced(
        self,
        matriculate_applicant: MatriculateApplicant,
        applicants: ApplicantRepositoryPort,
        events: InMemoryEventBus,
        cleared: Applicant,
    ) -> None:
        result = await matriculate_applicant.execute(MATRICULATE)

        stored = await applicants.get(APPLICANT_ID)
        assert stored is not None
        assert stored.status is ApplicationStatus.MATRICULATED
        assert result.program_id == COMPUTER_SCIENCE
        assert events.published == (
            StudentMatriculated(
                applicant_id=APPLICANT_ID,
                program_id=COMPUTER_SCIENCE,
                session_id=SESSION_ID,
                bio_data=BIO,
            ),
        )

    async def test_the_event_carries_bio_data_and_no_matric_number(
        self,
        matriculate_applicant: MatriculateApplicant,
        events: InMemoryEventBus,
        cleared: Applicant,
    ) -> None:
        """Issuing the number is Student Profile's job; an event carrying one would mean
        Admissions had already done it."""
        await matriculate_applicant.execute(MATRICULATE)

        (published,) = events.published
        assert published.bio_data.full_name == "Adaeze Okonkwo"
        assert not hasattr(published, "matric_number")
        assert not hasattr(published, "student_id")

    async def test_the_announced_program_is_the_offered_one(
        self,
        matriculate_applicant: MatriculateApplicant,
        applicants: ApplicantRepositoryPort,
        events: InMemoryEventBus,
    ) -> None:
        await applicants.add(a_cleared_applicant(MATHEMATICS))

        await matriculate_applicant.execute(MATRICULATE)

        (published,) = events.published
        assert published.program_id == MATHEMATICS

    async def test_an_uncleared_applicant_is_refused(
        self,
        matriculate_applicant: MatriculateApplicant,
        events: InMemoryEventBus,
        accepted: Applicant,
    ) -> None:
        """The gate this whole split exists to hold. Nothing is announced either."""
        with pytest.raises(AcceptanceFeeNotClearedError):
            await matriculate_applicant.execute(MATRICULATE)

        assert events.published == ()

    async def test_an_applicant_who_never_accepted_is_refused(
        self,
        matriculate_applicant: MatriculateApplicant,
        applicants: ApplicantRepositoryPort,
    ) -> None:
        await applicants.add(an_applicant())
        with pytest.raises(OfferNotAcceptedError):
            await matriculate_applicant.execute(MATRICULATE)

    async def test_matriculating_twice_is_refused(
        self, matriculate_applicant: MatriculateApplicant, cleared: Applicant
    ) -> None:
        await matriculate_applicant.execute(MATRICULATE)
        with pytest.raises(ApplicationOutcomeFinalError):
            await matriculate_applicant.execute(MATRICULATE)

    async def test_an_unknown_applicant_is_an_error(
        self, matriculate_applicant: MatriculateApplicant
    ) -> None:
        with pytest.raises(ApplicantNotFoundError, match=APPLICANT_ID):
            await matriculate_applicant.execute(MATRICULATE)
