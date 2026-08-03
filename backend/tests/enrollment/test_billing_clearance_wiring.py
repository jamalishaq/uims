"""Enrollment's clearance question answered by a real Billing ledger.

The build playbook's Phase 5.2 line: "Replace the ``FinancialClearancePort`` stub with the real
adapter". ``tests/enrollment/adapters/test_billing_financial_clearance_adapter.py`` tests the
rule against figures stated outright; this module tests it against figures a real ``Account``
worked out — a published ``FeeSchedule``, an offer accepted, a session opened, and payments
allocated by Billing's own gating-charge-first order.

It is a test rather than production code for the reason the dependency rule gives: no module
under ``src/enrollment/`` may import ``billing``, at any layer, ``if TYPE_CHECKING`` included.
So the introduction has to be made by somebody outside both contexts, and that somebody is
:class:`BillingSessionFeeLedger` below. It is the composition root for this port, in a dozen
lines, and it is the *only* thing Phase 6 replaces: a client against Billing's read model goes
here, and neither the adapter nor a line of Enrollment moves.

Worth noticing what crosses and what does not. ``ChargeKind.SESSION`` and ``Money`` are named
here and nowhere in Enrollment; ``Term`` and :class:`SessionFeePosition` are named here and
nowhere in Billing. Neither context can see the other's vocabulary, and this module can see
both — which is what makes it wiring.

**The fee amounts are test fixtures, not institutional facts** (CLAUDE.md section 6). They are
round so that a reader can check a percentage in their head.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from billing.adapters.outbound import (
    InMemoryAccountRepository,
    InMemoryEventPublisher,
    InMemoryFeeScheduleRepository,
)
from billing.application import (
    ApplySessionFees,
    LinkStudentAccount,
    LinkStudentAccountCommand,
    OpenAccountForOffer,
    OpenAccountForOfferCommand,
    ReadAccount,
    RecordPayment,
    RecordPaymentCommand,
)
from billing.domain import ChargeKind, FeeSchedule, Level, Money, SessionFeeLine
from enrollment.adapters.outbound import (
    BillingFinancialClearanceAdapter,
    SessionFeePosition,
)
from enrollment.domain import SemesterOrdinal, Term

APPLICANT_ID = "app-2026-0001"
MATRIC_NUMBER = "260591001"
SESSION_ID = "sess-2026"
CSC_PROGRAM_ID = "prog-csc-bsc"
LAW_PROGRAM_ID = "prog-law-llb"

ACCEPTANCE_FEE = Money(Decimal("20000"))
MATRICULATION_FEE = Money(Decimal("50000"))
CSC_SESSION_FEE = Money(Decimal("100000"))

FIRST = Term(session_id=SESSION_ID, semester_id="sem-2026-1", ordinal=SemesterOrdinal.FIRST)
SECOND = Term(session_id=SESSION_ID, semester_id="sem-2026-2", ordinal=SemesterOrdinal.SECOND)

ADMISSION_FEES = ACCEPTANCE_FEE + MATRICULATION_FEE
"""What has to be settled before a payment starts eating into the session fee."""


class BillingSessionFeeLedger:
    """The translation: Billing's statement in, Enrollment's fact out.

    Two figures cross and no more. ``AccountStatement`` also carries payments, an outstanding
    total and a credit balance, and every one of them is a number Enrollment could have built a
    different rule out of — so this hands over the session fee's amount and what has been
    allocated to it, and drops the rest on the floor.

    ``find`` rather than ``execute``, because a clearance check asked about somebody with no
    ledger is a normal question with a normal answer. ``None`` travels; an exception would put
    a fresher on an error path.
    """

    def __init__(self, accounts: ReadAccount) -> None:
        self._accounts = accounts

    def session_fee_for(self, party_id: str, session_id: str) -> SessionFeePosition | None:
        statement = self._accounts.find(party_id)
        if statement is None:
            return None
        charge = statement.charge_for(ChargeKind.SESSION, session_id)
        if charge is None:
            return None
        return SessionFeePosition(charged=charge.amount.amount, settled=charge.allocated.amount)


@pytest.fixture
def accounts() -> InMemoryAccountRepository:
    return InMemoryAccountRepository()


@pytest.fixture
def schedules() -> InMemoryFeeScheduleRepository:
    schedules = InMemoryFeeScheduleRepository()
    schedules.add(
        FeeSchedule.for_session(
            SESSION_ID,
            acceptance_fee=ACCEPTANCE_FEE,
            matriculation_fee=MATRICULATION_FEE,
            session_fees=(
                SessionFeeLine(program_id=CSC_PROGRAM_ID, level=Level(100), amount=CSC_SESSION_FEE),
            ),
        )
    )
    return schedules


@pytest.fixture
def events() -> InMemoryEventPublisher:
    return InMemoryEventPublisher()


@pytest.fixture
def pay(accounts: InMemoryAccountRepository, events: InMemoryEventPublisher) -> RecordPayment:
    return RecordPayment(accounts, events)


@pytest.fixture
def clearance_adapter(accounts: InMemoryAccountRepository) -> BillingFinancialClearanceAdapter:
    """The composition root, in one line. Everything above it is real on both sides.

    Named apart from ``tests/enrollment/conftest.py``'s ``clearance`` fixture on purpose: that
    one is the fake the application tests drive, and this one is the real adapter. Shadowing it
    here would make the difference between them invisible at a call site.
    """
    return BillingFinancialClearanceAdapter(BillingSessionFeeLedger(ReadAccount(accounts)))


@pytest.fixture
def billed_student(
    accounts: InMemoryAccountRepository,
    schedules: InMemoryFeeScheduleRepository,
    events: InMemoryEventPublisher,
) -> str:
    """An accepted offer, a session opened, and a ledger with three charges on it."""
    OpenAccountForOffer(accounts, schedules, events).execute(
        OpenAccountForOfferCommand(
            applicant_id=APPLICANT_ID, program_id=CSC_PROGRAM_ID, session_id=SESSION_ID
        )
    )
    ApplySessionFees(accounts, schedules, events).execute(SESSION_ID)
    return APPLICANT_ID


def a_payment(amount: Decimal, reference: str = "psk-0001") -> RecordPaymentCommand:
    return RecordPaymentCommand(
        party_id=APPLICANT_ID,
        gateway_ref=reference,
        amount=amount,
        received_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
    )


def settle_admission_fees_and_pay(pay: RecordPayment, towards_session_fee: Decimal) -> None:
    """Pay off the acceptance and matriculation charges, then put money on the session fee.

    Billing allocates gating-charge-first and then in the order raised, so a single payment of
    the admission fees plus ``towards_session_fee`` lands exactly ``towards_session_fee`` on the
    session charge. Two payments would do as well; one keeps the arithmetic in view.
    """
    pay.execute(a_payment(ADMISSION_FEES.amount + towards_session_fee))


class TestTheBoundariesHoldAgainstARealLedger:
    """The same 69/70/71 and 99/100 table, with the allocation done by ``Account``."""

    @pytest.mark.parametrize(
        ("towards_session_fee", "cleared"),
        [
            (Decimal("69000"), False),
            (Decimal("70000"), True),
            (Decimal("71000"), True),
        ],
        ids=["69%", "70%", "71%"],
    )
    def test_first_semester_at_the_seventy_percent_boundary(
        self,
        billed_student: str,
        pay: RecordPayment,
        clearance_adapter: BillingFinancialClearanceAdapter,
        towards_session_fee: Decimal,
        cleared: bool,
    ) -> None:
        settle_admission_fees_and_pay(pay, towards_session_fee)
        assert clearance_adapter.is_cleared_for_registration(billed_student, FIRST) is cleared

    @pytest.mark.parametrize(
        ("towards_session_fee", "cleared"),
        [
            (Decimal("99000"), False),
            (Decimal("100000"), True),
        ],
        ids=["99%", "100%"],
    )
    def test_second_semester_at_the_hundred_percent_boundary(
        self,
        billed_student: str,
        pay: RecordPayment,
        clearance_adapter: BillingFinancialClearanceAdapter,
        towards_session_fee: Decimal,
        cleared: bool,
    ) -> None:
        settle_admission_fees_and_pay(pay, towards_session_fee)
        assert clearance_adapter.is_cleared_for_registration(billed_student, SECOND) is cleared

    def test_the_deferred_thirty_percent_is_what_separates_the_halves(
        self,
        billed_student: str,
        pay: RecordPayment,
        clearance_adapter: BillingFinancialClearanceAdapter,
    ) -> None:
        """The rule read as a bursar states it: 70% registers you once, then settle up."""
        settle_admission_fees_and_pay(pay, Decimal("70000"))
        assert clearance_adapter.is_cleared_for_registration(billed_student, FIRST) is True
        assert clearance_adapter.is_cleared_for_registration(billed_student, SECOND) is False

        pay.execute(a_payment(Decimal("30000"), reference="psk-0002"))
        assert clearance_adapter.is_cleared_for_registration(billed_student, SECOND) is True

    def test_admission_fees_are_not_credited_to_the_session_fee(
        self,
        billed_student: str,
        pay: RecordPayment,
        clearance_adapter: BillingFinancialClearanceAdapter,
    ) -> None:
        """70,000 paid is not 70% of the session fee when 70,000 of it was owed elsewhere.

        The gating charge comes first, so this money settles the acceptance and matriculation
        fees and leaves nothing on the session fee. A rule computed from a total paid rather
        than from what was allocated to the session charge would clear this student.
        """
        pay.execute(a_payment(ADMISSION_FEES.amount))
        assert clearance_adapter.is_cleared_for_registration(billed_student, FIRST) is False


class TestAbsenceRefuses:
    def test_a_party_billing_has_never_heard_of_is_refused(
        self, clearance_adapter: BillingFinancialClearanceAdapter
    ) -> None:
        assert clearance_adapter.is_cleared_for_registration("stu-nobody", FIRST) is False

    def test_an_account_the_session_fee_never_reached_is_refused(
        self,
        accounts: InMemoryAccountRepository,
        schedules: InMemoryFeeScheduleRepository,
        events: InMemoryEventPublisher,
        pay: RecordPayment,
        clearance_adapter: BillingFinancialClearanceAdapter,
    ) -> None:
        """A ``(program, level)`` the schedule does not price is skipped by the batch.

        Billing reports it as ``unpriced`` and carries on, which is right — one hole in a
        schedule should not stop a session opening. What it leaves is an account with no
        session charge, and the answer to a clearance question about it is no.
        """
        OpenAccountForOffer(accounts, schedules, events).execute(
            OpenAccountForOfferCommand(
                applicant_id=APPLICANT_ID, program_id=LAW_PROGRAM_ID, session_id=SESSION_ID
            )
        )
        applied = ApplySessionFees(accounts, schedules, events).execute(SESSION_ID)
        assert applied.unpriced == (APPLICANT_ID,)

        pay.execute(a_payment(ADMISSION_FEES.amount))
        assert clearance_adapter.is_cleared_for_registration(APPLICANT_ID, FIRST) is False

    def test_a_fee_settled_for_another_session_does_not_clear_this_one(
        self,
        billed_student: str,
        pay: RecordPayment,
        clearance_adapter: BillingFinancialClearanceAdapter,
    ) -> None:
        settle_admission_fees_and_pay(pay, CSC_SESSION_FEE.amount)
        next_session = Term(
            session_id="sess-2027", semester_id="sem-2027-1", ordinal=SemesterOrdinal.FIRST
        )
        assert clearance_adapter.is_cleared_for_registration(billed_student, FIRST) is True
        assert clearance_adapter.is_cleared_for_registration(billed_student, next_session) is False


class TestClearanceSurvivesTheMatricNumberLink:
    """One continuous ledger, two ids. Enrollment only ever knows the second."""

    def test_the_matric_number_reaches_the_applicants_ledger(
        self,
        billed_student: str,
        accounts: InMemoryAccountRepository,
        pay: RecordPayment,
        clearance_adapter: BillingFinancialClearanceAdapter,
    ) -> None:
        settle_admission_fees_and_pay(pay, Decimal("70000"))
        assert clearance_adapter.is_cleared_for_registration(MATRIC_NUMBER, FIRST) is False

        LinkStudentAccount(accounts).execute(
            LinkStudentAccountCommand(party_id=billed_student, student_id=MATRIC_NUMBER)
        )
        assert clearance_adapter.is_cleared_for_registration(MATRIC_NUMBER, FIRST) is True
        assert clearance_adapter.is_cleared_for_registration(billed_student, FIRST) is True
