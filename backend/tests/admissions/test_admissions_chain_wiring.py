"""The whole admissions chain, over the real bus: accept → pay → matriculate → student.

This is the path that could not be walked at all before this phase. ``Applicant.accept()``,
``decline()``, ``matriculate()`` and ``record_acceptance_fee_paid()`` were domain methods with
no use case in front of them, so ``OfferAccepted`` was never published, ``OpenAccountForOffer``
— the only way an ``Account`` is ever created — was never reached, no acceptance fee was ever
paid, ``StudentMatriculated`` was never published, and the only way a student came into
existence was the manual registration route, bypassing admissions entirely.

Three contexts at once, which makes this a test rather than production code for the reason the
dependency rule gives: none of them may import another, so the introduction has to be made by
somebody outside all three. In a running process that somebody is ``src/main.py``; here it is
the ``wired`` fixture below.

Nothing is stubbed between the ends. Real use cases, real aggregates, real repositories, real
handlers. The only thing that is not real is the transport, and replacing that is a later
phase that touches one flat module.

**Admissions and Billing point at each other**, which is the shape worth seeing: Admissions
publishes ``OfferAccepted`` and Billing subscribes; Billing publishes ``AcceptanceFeePaid``
and Admissions subscribes. Neither imports the other. Both name a topic.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from admissions.adapters.inbound import ACCEPTANCE_FEE_PAID, AcceptanceFeePaidHandler
from admissions.adapters.outbound import InMemoryEventBus
from admissions.application import (
    AcceptOffer,
    AcceptOfferCommand,
    DeclineOffer,
    DeclineOfferCommand,
    MatriculateApplicant,
    MatriculateApplicantCommand,
    RecordAcceptanceFeePaid,
)
from admissions.domain import (
    AcceptanceFeeNotClearedError,
    AdmissionCycle,
    Applicant,
    ApplicationStatus,
    BioData,
    UtmeResult,
    UtmeSubjectScore,
)
from admissions.ports import AdmissionCycleRepositoryPort, ApplicantRepositoryPort
from billing.adapters.inbound import OFFER_ACCEPTED, OfferAcceptedHandler
from billing.adapters.outbound import InMemoryAccountRepository, InMemoryFeeScheduleRepository
from billing.adapters.outbound import InMemoryEventBus as BillingEventBus
from billing.application import OpenAccountForOffer, RecordPayment, RecordPaymentCommand
from billing.domain import ChargeKind, FeeSchedule, Level, Money, SessionFeeLine
from event_bus import EventBus
from student_profile.adapters.inbound import STUDENT_MATRICULATED, StudentMatriculatedHandler
from student_profile.adapters.outbound import (
    InMemoryDepartmentCodeAdapter,
    InMemoryMatricSequenceRepository,
    InMemoryStudentRepository,
)
from student_profile.application import RegisterNewStudent
from student_profile.domain import MatricNumberIssuer
from student_profile.ports import StudentRepositoryPort

APPLICANT_ID = "app-0001"
COMPUTER_SCIENCE = "prg-csc"
SESSION_ID = "sess-2026"
CSC_CODE = "0591"

ACCEPT = AcceptOfferCommand(APPLICANT_ID)
DECLINE = DeclineOfferCommand(APPLICANT_ID)
MATRICULATE = MatriculateApplicantCommand(APPLICANT_ID)

ACCEPTANCE_FEE = Money(Decimal("20000"))
MATRICULATION_FEE = Money(Decimal("50000"))
SESSION_FEE = Money(Decimal("100000"))
"""Test fixtures, not institutional facts. Real fees arrive on a published schedule."""

BIO = BioData("Adaeze Okonkwo", date_of_birth=date(2006, 4, 1), email="adaeze@example.com")
SUBJECTS = ("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", "BIOLOGY")


class Wired:
    """Everything the three contexts need, introduced to each other over one bus."""

    def __init__(
        self,
        bus: EventBus,
        accept_offer: AcceptOffer,
        decline_offer: DeclineOffer,
        matriculate_applicant: MatriculateApplicant,
        record_payment: RecordPayment,
        accounts: InMemoryAccountRepository,
        students: StudentRepositoryPort,
    ) -> None:
        self.bus = bus
        self.accept_offer = accept_offer
        self.decline_offer = decline_offer
        self.matriculate_applicant = matriculate_applicant
        self.record_payment = record_payment
        self.accounts = accounts
        self.students = students


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def events(bus: EventBus) -> InMemoryEventBus:
    """Overrides the Admissions conftest fixture so this context publishes onto the shared bus.

    ``accept_offer`` and ``matriculate_applicant`` come from ``tests/admissions/conftest.py``
    unchanged and cannot tell the difference — the port is "deliberately ignorant of who
    listens", and that they still work here is the port doing its job.
    """
    return InMemoryEventBus(bus)


@pytest.fixture
async def offered(applicants: ApplicantRepositoryPort) -> Applicant:
    applicant = Applicant.apply(
        applicant_id=APPLICANT_ID,
        applied_program_id=COMPUTER_SCIENCE,
        session_id=SESSION_ID,
        bio_data=BIO,
        utme_result=UtmeResult(tuple(UtmeSubjectScore(subject, 70) for subject in SUBJECTS)),
    )
    applicant.screen()
    applicant.offer(COMPUTER_SCIENCE)
    await applicants.add(applicant)
    return applicant


@pytest.fixture
async def claimed_cycle(cycles: AdmissionCycleRepositoryPort) -> AdmissionCycle:
    cycle = AdmissionCycle(COMPUTER_SCIENCE, SESSION_ID, 2, offers_made=1)
    await cycles.add(cycle)
    return cycle


@pytest.fixture
async def wired(
    bus: EventBus,
    accept_offer: AcceptOffer,
    decline_offer: DeclineOffer,
    matriculate_applicant: MatriculateApplicant,
    record_acceptance_fee_paid: RecordAcceptanceFeePaid,
) -> Wired:
    """The composition root for this test: three contexts, one bus, five subscriptions' worth.

    Billing's and Student Profile's adapters are built here rather than taken from their own
    conftests, because those fixtures are not in scope for this package and importing them
    would couple two otherwise independent suites — the argument
    ``tests/academic_records/test_grade_submitted_wiring.py`` already makes.
    """
    accounts = InMemoryAccountRepository()
    schedules = InMemoryFeeScheduleRepository()
    await schedules.add(
        FeeSchedule.for_session(
            SESSION_ID,
            acceptance_fee=ACCEPTANCE_FEE,
            matriculation_fee=MATRICULATION_FEE,
            session_fees=(
                SessionFeeLine(program_id=COMPUTER_SCIENCE, level=Level(100), amount=SESSION_FEE),
            ),
        )
    )
    billing_events = BillingEventBus(bus)
    open_account_for_offer = OpenAccountForOffer(accounts, schedules, billing_events)
    record_payment = RecordPayment(accounts, billing_events)

    students = InMemoryStudentRepository()
    departments = InMemoryDepartmentCodeAdapter()
    departments.register(COMPUTER_SCIENCE, SESSION_ID, CSC_CODE, 2026)
    register_new_student = RegisterNewStudent(
        students=students,
        sequences=InMemoryMatricSequenceRepository(),
        departments=departments,
        issuer=MatricNumberIssuer(),
    )

    bus.subscribe(OFFER_ACCEPTED, OfferAcceptedHandler(open_account_for_offer).on_message)
    bus.subscribe(
        STUDENT_MATRICULATED,
        StudentMatriculatedHandler(register_new_student, students).on_message,
    )
    bus.subscribe(
        ACCEPTANCE_FEE_PAID, AcceptanceFeePaidHandler(record_acceptance_fee_paid).on_message
    )

    return Wired(
        bus=bus,
        accept_offer=accept_offer,
        decline_offer=decline_offer,
        matriculate_applicant=matriculate_applicant,
        record_payment=record_payment,
        accounts=accounts,
        students=students,
    )


async def pay(wired: Wired, amount: Money, ref: str = "psk-ref-0001") -> None:
    await wired.record_payment.execute(
        RecordPaymentCommand(
            party_id=APPLICANT_ID,
            gateway_ref=ref,
            amount=amount.amount,
            received_at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        )
    )


# ---- the path this phase exists to build ----


async def test_the_whole_chain_from_offer_to_student(
    wired: Wired, applicants: ApplicantRepositoryPort, offered: Applicant
) -> None:
    """The phase in one test: an offer held becomes a student with a matric number."""
    assert await wired.students.find_by_applicant(APPLICANT_ID) is None

    await wired.accept_offer.execute(ACCEPT)
    await pay(wired, ACCEPTANCE_FEE)
    await wired.matriculate_applicant.execute(MATRICULATE)

    applicant = await applicants.get(APPLICANT_ID)
    student = await wired.students.find_by_applicant(APPLICANT_ID)
    assert applicant is not None and student is not None
    assert applicant.status is ApplicationStatus.MATRICULATED
    assert student.program_id == COMPUTER_SCIENCE
    assert str(student.matric_number).startswith("26" + CSC_CODE)


async def test_accepting_opens_a_ledger_with_both_admission_charges(
    wired: Wired, offered: Applicant
) -> None:
    """``OpenAccountForOffer`` is reachable only from ``OfferAccepted``, and now it is reached."""
    assert await wired.accounts.get(APPLICANT_ID) is None

    await wired.accept_offer.execute(ACCEPT)

    account = await wired.accounts.get(APPLICANT_ID)
    assert account is not None
    assert [charge.kind for charge in account.charges] == [
        ChargeKind.ACCEPTANCE,
        ChargeKind.MATRICULATION,
    ]


async def test_paying_the_acceptance_fee_reaches_back_to_admissions(
    wired: Wired, applicants: ApplicantRepositoryPort, offered: Applicant
) -> None:
    """The other direction of the loop: Billing publishes, Admissions consumes."""
    await wired.accept_offer.execute(ACCEPT)

    await pay(wired, ACCEPTANCE_FEE)

    applicant = await applicants.get(APPLICANT_ID)
    assert applicant is not None
    assert applicant.is_fee_cleared is True
    assert applicant.status is ApplicationStatus.ACCEPTED


async def test_the_matriculation_fee_does_not_gate_anything(
    wired: Wired, applicants: ApplicantRepositoryPort, offered: Applicant
) -> None:
    """CLAUDE.md section 4: only the acceptance fee gates matriculation. The larger,
    still-outstanding matriculation fee must not hold anybody up."""
    await wired.accept_offer.execute(ACCEPT)
    await pay(wired, ACCEPTANCE_FEE)

    await wired.matriculate_applicant.execute(MATRICULATE)

    account = await wired.accounts.get(APPLICANT_ID)
    assert account is not None
    assert any(
        charge.kind is ChargeKind.MATRICULATION and charge.outstanding.amount > 0
        for charge in account.charges
    )
    assert await wired.students.find_by_applicant(APPLICANT_ID) is not None


# ---- what must not happen ----


async def test_matriculation_is_refused_before_the_fee_clears(
    wired: Wired, offered: Applicant
) -> None:
    """The gate holds across the whole wiring, not just in the aggregate's unit test."""
    await wired.accept_offer.execute(ACCEPT)

    with pytest.raises(AcceptanceFeeNotClearedError):
        await wired.matriculate_applicant.execute(MATRICULATE)

    assert await wired.students.find_by_applicant(APPLICANT_ID) is None


async def test_a_short_payment_clears_nothing(
    wired: Wired, applicants: ApplicantRepositoryPort, offered: Applicant
) -> None:
    """ "Intent confirmed" never implies "charge settled" — the ledger evaluates balances."""
    await wired.accept_offer.execute(ACCEPT)

    await pay(wired, Money(Decimal("19999")))

    applicant = await applicants.get(APPLICANT_ID)
    assert applicant is not None
    assert applicant.is_fee_cleared is False


async def test_a_replayed_matriculation_issues_no_second_matric_number(
    wired: Wired, offered: Applicant
) -> None:
    """At-least-once delivery replayed by hand. Two matric numbers for one person is the
    failure this must not have."""
    await wired.accept_offer.execute(ACCEPT)
    await pay(wired, ACCEPTANCE_FEE)
    await wired.matriculate_applicant.execute(MATRICULATE)
    first = await wired.students.find_by_applicant(APPLICANT_ID)
    assert first is not None

    await wired.bus.publish(wired.bus.published[-1])

    second = await wired.students.find_by_applicant(APPLICANT_ID)
    assert second is not None
    assert second.student_id == first.student_id
    assert str(second.matric_number) == str(first.matric_number)


async def test_a_declined_offer_opens_no_ledger_and_returns_the_place(
    wired: Wired,
    cycles: AdmissionCycleRepositoryPort,
    offered: Applicant,
    claimed_cycle: AdmissionCycle,
) -> None:
    """Declining publishes nothing, so Billing never hears of an applicant who said no."""
    await wired.decline_offer.execute(DECLINE)

    cycle = await cycles.get(COMPUTER_SCIENCE, SESSION_ID)
    assert cycle is not None
    assert cycle.offers_made == 0
    assert await wired.accounts.get(APPLICANT_ID) is None
    assert wired.bus.published == ()


# ---- the boundary the wiring must not cross ----


async def test_bio_data_crosses_as_nested_primitives(wired: Wired, offered: Applicant) -> None:
    """``StudentMatriculated`` carries a ``BioData``; what a subscriber sees is a mapping.

    Flattening it is Student Profile's translation to do, which is what makes that handler an
    anti-corruption layer rather than a shared mapping table.
    """
    seen: list[object] = []

    async def watching(payload: object) -> None:
        seen.append(payload)

    wired.bus.subscribe(STUDENT_MATRICULATED, watching)  # type: ignore[arg-type]

    await wired.accept_offer.execute(ACCEPT)
    await pay(wired, ACCEPTANCE_FEE)
    await wired.matriculate_applicant.execute(MATRICULATE)

    (payload,) = seen
    assert payload == {
        "applicant_id": APPLICANT_ID,
        "program_id": COMPUTER_SCIENCE,
        "session_id": SESSION_ID,
        "bio_data": {
            "full_name": "Adaeze Okonkwo",
            "date_of_birth": date(2006, 4, 1),
            "email": "adaeze@example.com",
            "phone_number": None,
        },
    }


def test_the_wiring_names_events_by_string_rather_than_by_type(wired: Wired) -> None:
    """A type is exactly the thing that cannot cross a context boundary."""
    assert wired.bus.subscribers_for(OFFER_ACCEPTED)
    assert wired.bus.subscribers_for(STUDENT_MATRICULATED)
    assert wired.bus.subscribers_for(ACCEPTANCE_FEE_PAID)
    assert wired.bus.subscribers_for("GradeSubmitted") == ()
