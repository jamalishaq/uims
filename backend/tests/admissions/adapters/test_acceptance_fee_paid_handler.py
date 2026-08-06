"""The one thing Admissions consumes: Billing saying the gating fee cleared.

What is worth proving about a handler is not that it works but that it is *not a second way
of doing the thing*. This one calls the same use case, so it cannot drift into unlocking
matriculation on terms the domain would refuse — and, more importantly here, it cannot
matriculate anybody. CLAUDE.md section 4 forbids auto-matriculation on payment, and a
handler that reached one method further would be exactly that.
"""

from datetime import date

import pytest

from admissions.adapters.inbound import (
    ACCEPTANCE_FEE_PAID,
    AcceptanceFeePaidHandler,
    AcceptanceFeePaidMessage,
)
from admissions.application import RecordAcceptanceFeePaid
from admissions.domain import (
    Applicant,
    ApplicationStatus,
    BioData,
    OfferNotAcceptedError,
    UtmeResult,
    UtmeSubjectScore,
)
from admissions.ports import ApplicantRepositoryPort

APPLICANT_ID = "app-0001"
COMPUTER_SCIENCE = "prg-csc"
SESSION_ID = "sess-2026"

BIO = BioData("Adaeze Okonkwo", date_of_birth=date(2006, 4, 1))
SUBJECTS = ("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", "BIOLOGY")


def an_accepted_applicant() -> Applicant:
    applicant = Applicant.apply(
        applicant_id=APPLICANT_ID,
        applied_program_id=COMPUTER_SCIENCE,
        session_id=SESSION_ID,
        bio_data=BIO,
        utme_result=UtmeResult(tuple(UtmeSubjectScore(subject, 70) for subject in SUBJECTS)),
    )
    applicant.screen()
    applicant.offer(COMPUTER_SCIENCE)
    applicant.accept()
    return applicant


@pytest.fixture
def handler(record_acceptance_fee_paid: RecordAcceptanceFeePaid) -> AcceptanceFeePaidHandler:
    return AcceptanceFeePaidHandler(record_acceptance_fee_paid)


@pytest.fixture
async def accepted(applicants: ApplicantRepositoryPort) -> Applicant:
    applicant = an_accepted_applicant()
    await applicants.add(applicant)
    return applicant


def test_subscribes_under_the_publisher_s_own_event_name() -> None:
    assert ACCEPTANCE_FEE_PAID == "AcceptanceFeePaid"


def test_reads_the_applicant_off_the_payload() -> None:
    message = AcceptanceFeePaidMessage.from_payload({"applicant_id": APPLICANT_ID})
    assert message == AcceptanceFeePaidMessage(applicant_id=APPLICANT_ID)


def test_ignores_fields_a_publisher_adds_later() -> None:
    message = AcceptanceFeePaidMessage.from_payload(
        {"applicant_id": APPLICANT_ID, "amount": "50000.00", "settled_at": "2026-08-01"}
    )
    assert message.applicant_id == APPLICANT_ID


def test_a_missing_applicant_raises_rather_than_defaulting() -> None:
    """An applicant quietly defaulted into shape would unlock matriculation for the wrong
    person."""
    with pytest.raises(KeyError):
        AcceptanceFeePaidMessage.from_payload({"amount": "50000.00"})


async def test_it_sets_the_flag_without_matriculating(
    handler: AcceptanceFeePaidHandler,
    applicants: ApplicantRepositoryPort,
    accepted: Applicant,
) -> None:
    """CLAUDE.md section 4: do not auto-matriculate on payment."""
    await handler.handle(AcceptanceFeePaidMessage(applicant_id=APPLICANT_ID))

    stored = await applicants.get(APPLICANT_ID)
    assert stored is not None
    assert stored.is_fee_cleared is True
    assert stored.status is ApplicationStatus.ACCEPTED


async def test_on_message_deserialises_then_handles(
    handler: AcceptanceFeePaidHandler,
    applicants: ApplicantRepositoryPort,
    accepted: Applicant,
) -> None:
    """The signature a bus calls, which is what lets the wiring be one line in the root."""
    await handler.on_message({"applicant_id": APPLICANT_ID})

    stored = await applicants.get(APPLICANT_ID)
    assert stored is not None
    assert stored.is_fee_cleared is True


async def test_redelivery_clears_nothing_twice(
    handler: AcceptanceFeePaidHandler, accepted: Applicant
) -> None:
    first = await handler.handle(AcceptanceFeePaidMessage(applicant_id=APPLICANT_ID))
    second = await handler.handle(AcceptanceFeePaidMessage(applicant_id=APPLICANT_ID))

    assert (first.was_already_cleared, second.was_already_cleared) == (False, True)


async def test_a_payment_for_somebody_who_never_accepted_surfaces(
    handler: AcceptanceFeePaidHandler, applicants: ApplicantRepositoryPort
) -> None:
    """Not swallowed: money against an applicant who owes no acceptance fee is a question
    for a person, and a handler that shrugged would lose it."""
    applicant = Applicant.apply(
        applicant_id=APPLICANT_ID,
        applied_program_id=COMPUTER_SCIENCE,
        session_id=SESSION_ID,
        bio_data=BIO,
        utme_result=UtmeResult(tuple(UtmeSubjectScore(subject, 70) for subject in SUBJECTS)),
    )
    await applicants.add(applicant)

    with pytest.raises(OfferNotAcceptedError):
        await handler.handle(AcceptanceFeePaidMessage(applicant_id=APPLICANT_ID))
