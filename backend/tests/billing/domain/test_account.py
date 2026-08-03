"""The ``Account`` aggregate, and the three claims Phase 5.1 exists to make good on.

CLAUDE.md section 6 names the payment ledger's idempotency invariant as something to escalate
before touching. This module is where that invariant is written down: **the same
``gateway_ref`` applied twice changes the ledger once**, **overpayment yields a credit
balance**, and **``AcceptanceFeePaid`` fires exactly once per applicant**. Each has a class of
its own below, and each asserts on the aggregate's own figures rather than on a repository —
the invariant lives here, so it is checkable with no infrastructure at all.

The amounts are round numbers so the arithmetic can be checked by eye. They are test fixtures
and not fees: what LASU actually charges is an institutional fact that arrives on a published
schedule (CLAUDE.md section 6).
"""

from datetime import datetime
from decimal import Decimal

import pytest

from billing.domain import (
    AcceptanceFeePaid,
    Account,
    ChargeAlreadyRaised,
    ChargeKind,
    ChargeRaised,
    DuplicatePaymentIgnored,
    InvalidChargeError,
    InvalidPaymentError,
    Level,
    MissingIdentifierError,
    Money,
    PartyAlreadyLinkedError,
    PaymentApplied,
)

APPLICANT_ID = "app-0001"
MATRIC_NUMBER = "260591001"
PROGRAM_ID = "prog-csc-bsc"
SESSION_ID = "sess-2026"
NEXT_SESSION_ID = "sess-2027"

ACCEPTANCE_FEE = Money(Decimal("20000"))
MATRICULATION_FEE = Money(Decimal("50000"))
SESSION_FEE = Money(Decimal("100000"))

AUGUST = datetime(2026, 8, 1, 9, 30)
SEPTEMBER = datetime(2026, 9, 1, 9, 30)


def naira(amount: str) -> Money:
    return Money(Decimal(amount))


def an_account() -> Account:
    return Account.open(APPLICANT_ID, PROGRAM_ID)


def an_admitted_account() -> Account:
    """What ``OfferAccepted`` leaves behind: both admission charges, nothing paid."""
    account = an_account()
    account.raise_acceptance_fee(SESSION_ID, ACCEPTANCE_FEE)
    account.raise_matriculation_fee(SESSION_ID, MATRICULATION_FEE)
    return account


def pay(account: Account, amount: str, *, ref: str, when: datetime = AUGUST) -> object:
    return account.apply_payment(gateway_ref=ref, amount=naira(amount), received_at=when)


class TestOpening:
    def test_opens_empty_at_the_entry_level(self) -> None:
        account = an_account()
        assert account.party_id == APPLICANT_ID
        assert account.program_id == PROGRAM_ID
        assert account.level == Level(100)
        assert account.charges == ()
        assert account.payments == ()
        assert account.outstanding == Money.zero()
        assert account.credit_balance == Money.zero()

    def test_a_level_may_be_stated_instead_of_defaulted(self) -> None:
        assert Account.open(APPLICANT_ID, PROGRAM_ID, level=Level(300)).level == Level(300)

    def test_answers_to_its_party_id_alone_before_matriculation(self) -> None:
        assert an_account().party_ids == frozenset({APPLICANT_ID})
        assert an_account().student_id is None

    @pytest.mark.parametrize("party_id", ["", "   "])
    def test_refuses_a_blank_party(self, party_id: str) -> None:
        with pytest.raises(MissingIdentifierError):
            Account.open(party_id, PROGRAM_ID)

    def test_refuses_a_blank_program(self) -> None:
        with pytest.raises(MissingIdentifierError):
            Account.open(APPLICANT_ID, "  ")

    def test_refuses_a_level_that_is_not_one(self) -> None:
        with pytest.raises(InvalidChargeError):
            Account.open(APPLICANT_ID, PROGRAM_ID, level=100)  # type: ignore[arg-type]


class TestRaisingCharges:
    def test_an_accepted_offer_leaves_two_charges_and_one_of_them_gates(self) -> None:
        account = an_admitted_account()
        assert [charge.kind for charge in account.charges] == [
            ChargeKind.ACCEPTANCE,
            ChargeKind.MATRICULATION,
        ]
        assert account.total_charged == naira("70000")
        assert account.outstanding == naira("70000")
        assert not account.acceptance_fee_settled

    def test_the_same_charge_raised_twice_is_a_no_op(self) -> None:
        """What a redelivered ``OfferAccepted`` or ``SessionOpened`` does: nobody is billed
        twice."""
        account = an_admitted_account()
        outcome = account.raise_acceptance_fee(SESSION_ID, ACCEPTANCE_FEE)
        assert isinstance(outcome, ChargeAlreadyRaised)
        assert len(account.charges) == 2
        assert account.total_charged == naira("70000")

    def test_a_charge_already_raised_is_not_re_priced(self) -> None:
        """A republished schedule does not rewrite a bill somebody may already have paid."""
        account = an_admitted_account()
        account.raise_acceptance_fee(SESSION_ID, naira("999999"))
        assert account.charge_for(ChargeKind.ACCEPTANCE, SESSION_ID).amount == ACCEPTANCE_FEE  # type: ignore[union-attr]

    def test_the_same_kind_in_another_session_is_a_different_charge(self) -> None:
        """Session fees accumulate year on year on one continuous ledger."""
        account = an_admitted_account()
        account.raise_session_fee(SESSION_ID, SESSION_FEE)
        outcome = account.raise_session_fee(NEXT_SESSION_ID, SESSION_FEE)
        assert isinstance(outcome, ChargeRaised)
        assert len(account.charges_for_session(NEXT_SESSION_ID)) == 1
        assert account.total_charged == naira("270000")

    def test_refuses_a_charge_for_nothing(self) -> None:
        with pytest.raises(InvalidChargeError):
            an_account().raise_session_fee(SESSION_ID, Money.zero())


class TestAllocation:
    def test_the_gating_charge_is_paid_before_anything_else(self) -> None:
        """A payment names no charge, so the account decides — in favour of what is holding
        something up."""
        account = an_admitted_account()
        outcome = pay(account, "20000", ref="ref-1")
        assert isinstance(outcome, PaymentApplied)
        assert [allocation.kind for allocation in outcome.allocations] == [ChargeKind.ACCEPTANCE]
        assert account.acceptance_fee_settled
        assert account.charge_for(ChargeKind.MATRICULATION, SESSION_ID).allocated.is_zero  # type: ignore[union-attr]

    def test_the_gating_charge_is_paid_first_even_when_it_was_raised_second(self) -> None:
        """The order is a policy, not an accident of which charge went on the list first."""
        account = Account.open(APPLICANT_ID, PROGRAM_ID)
        account.raise_matriculation_fee(SESSION_ID, MATRICULATION_FEE)
        account.raise_acceptance_fee(SESSION_ID, ACCEPTANCE_FEE)

        outcome = pay(account, "20000", ref="ref-1")

        assert isinstance(outcome, PaymentApplied)
        assert [allocation.kind for allocation in outcome.allocations] == [ChargeKind.ACCEPTANCE]

    def test_once_the_gating_charge_is_settled_the_rest_are_paid_in_the_order_raised(self) -> None:
        account = an_admitted_account()
        account.raise_session_fee(SESSION_ID, SESSION_FEE)

        outcome = pay(account, "80000", ref="ref-1")

        assert isinstance(outcome, PaymentApplied)
        assert [allocation.kind for allocation in outcome.allocations] == [
            ChargeKind.ACCEPTANCE,
            ChargeKind.MATRICULATION,
            ChargeKind.SESSION,
        ]
        assert account.charge_for(ChargeKind.SESSION, SESSION_ID).allocated == naira("10000")  # type: ignore[union-attr]

    def test_a_part_payment_leaves_the_charge_outstanding(self) -> None:
        account = an_admitted_account()
        pay(account, "5000", ref="ref-1")
        assert account.charge_for(ChargeKind.ACCEPTANCE, SESSION_ID).outstanding == naira("15000")  # type: ignore[union-attr]
        assert not account.acceptance_fee_settled
        assert account.outstanding == naira("65000")

    def test_the_totals_add_up_after_every_allocation(self) -> None:
        account = an_admitted_account()
        pay(account, "30000", ref="ref-1")
        assert account.total_paid == naira("30000")
        assert account.total_allocated == naira("30000")
        assert account.total_charged == naira("70000")
        assert account.outstanding == naira("40000")
        assert account.credit_balance == Money.zero()


class TestIdempotency:
    """The invariant CLAUDE.md section 6 says to escalate before touching."""

    def test_the_same_duplicate_gateway_ref_applied_twice_changes_the_ledger_once(self) -> None:
        account = an_admitted_account()
        first = pay(account, "20000", ref="pay-abc-123")

        before = (
            account.payments,
            account.total_paid,
            account.total_allocated,
            account.outstanding,
            account.credit_balance,
            account.charges,
        )
        second = pay(account, "20000", ref="pay-abc-123", when=SEPTEMBER)

        assert isinstance(first, PaymentApplied)
        assert isinstance(second, DuplicatePaymentIgnored)
        assert (
            account.payments,
            account.total_paid,
            account.total_allocated,
            account.outstanding,
            account.credit_balance,
            account.charges,
        ) == before
        assert len(account.payments) == 1

    def test_a_duplicate_gateway_ref_is_ignored_rather_than_refused(self) -> None:
        """Silent, in CLAUDE.md's sense: a webhook retry is traffic, not an incident."""
        account = an_admitted_account()
        pay(account, "20000", ref="pay-abc-123")
        outcome = pay(account, "20000", ref="pay-abc-123")
        assert isinstance(outcome, DuplicatePaymentIgnored)
        assert outcome.original.received_at == AUGUST
        assert outcome.events == ()

    def test_a_duplicate_gateway_ref_carrying_a_different_amount_still_changes_nothing(
        self,
    ) -> None:
        """The reference is the identity of the movement of money. Noticing the discrepancy is
        reconciliation's job in Phase 5.3, not this method's."""
        account = an_admitted_account()
        pay(account, "20000", ref="pay-abc-123")
        outcome = pay(account, "999999", ref="pay-abc-123")
        assert isinstance(outcome, DuplicatePaymentIgnored)
        assert account.total_paid == naira("20000")

    def test_a_duplicate_gateway_ref_is_ignored_before_the_amount_is_even_read(self) -> None:
        """A replay carrying a malformed amount is ignored, not rejected."""
        account = an_admitted_account()
        pay(account, "20000", ref="pay-abc-123")
        outcome = account.apply_payment(
            gateway_ref="pay-abc-123",
            amount=Money.zero(),
            received_at=SEPTEMBER,
        )
        assert isinstance(outcome, DuplicatePaymentIgnored)

    def test_two_different_references_both_land(self) -> None:
        """The guard is the reference, not the amount: two people may pay the same figure."""
        account = an_admitted_account()
        pay(account, "20000", ref="ref-1")
        pay(account, "20000", ref="ref-2")
        assert account.total_paid == naira("40000")

    def test_refuses_a_payment_with_no_reference(self) -> None:
        with pytest.raises(MissingIdentifierError):
            pay(an_admitted_account(), "20000", ref="  ")

    def test_refuses_a_payment_of_nothing(self) -> None:
        """A zero payment moves no money and would still consume its reference."""
        with pytest.raises(InvalidPaymentError):
            pay(an_admitted_account(), "0", ref="ref-1")


class TestSurplus:
    """The ledger allows surplus: never assume balance ≤ charges."""

    def test_an_overpayment_yields_a_credit_balance(self) -> None:
        account = an_admitted_account()
        outcome = pay(account, "100000", ref="ref-1")

        assert isinstance(outcome, PaymentApplied)
        assert account.outstanding == Money.zero()
        assert account.credit_balance == naira("30000")
        assert outcome.credited == naira("30000")
        assert account.total_paid == naira("100000")
        assert account.total_allocated == naira("70000")

    def test_an_overpayment_on_an_account_with_nothing_outstanding_is_all_credit(self) -> None:
        account = an_admitted_account()
        pay(account, "70000", ref="ref-1")
        pay(account, "5000", ref="ref-2")
        assert account.credit_balance == naira("5000")
        assert account.outstanding == Money.zero()

    def test_credit_from_an_overpayment_is_absorbed_by_the_next_charge_raised(self) -> None:
        """Which is what turns an overpayment at acceptance into a part-paid session fee, rather
        than a balance somebody has to remember to spend."""
        account = an_admitted_account()
        pay(account, "100000", ref="ref-1")

        outcome = account.raise_session_fee(SESSION_ID, SESSION_FEE)

        assert isinstance(outcome, ChargeRaised)
        assert outcome.settled_from_credit == naira("30000")
        assert outcome.charge.outstanding == naira("70000")
        assert account.credit_balance == Money.zero()

    def test_credit_larger_than_the_next_charge_stays_credit(self) -> None:
        account = an_admitted_account()
        pay(account, "200000", ref="ref-1")
        account.raise_session_fee(SESSION_ID, SESSION_FEE)
        assert account.credit_balance == naira("30000")
        assert account.outstanding == Money.zero()

    def test_a_payment_on_an_account_with_no_charges_at_all_is_credit(self) -> None:
        account = an_account()
        outcome = pay(account, "20000", ref="ref-1")
        assert isinstance(outcome, PaymentApplied)
        assert outcome.allocations == ()
        assert account.credit_balance == naira("20000")


class TestAcceptanceFeePaid:
    """Exactly once per applicant, and structurally rather than by a flag."""

    def test_the_payment_that_settles_the_acceptance_fee_produces_the_fact(self) -> None:
        account = an_admitted_account()
        outcome = pay(account, "20000", ref="ref-1")
        assert isinstance(outcome, PaymentApplied)
        assert outcome.events == (AcceptanceFeePaid(applicant_id=APPLICANT_ID),)

    def test_part_payments_before_it_produce_nothing(self) -> None:
        account = an_admitted_account()
        first = pay(account, "15000", ref="ref-1")
        assert isinstance(first, PaymentApplied)
        assert first.events == ()
        assert not account.acceptance_fee_settled

    def test_fires_once_across_a_whole_sequence_of_payments(self) -> None:
        account = an_admitted_account()
        account.raise_session_fee(SESSION_ID, SESSION_FEE)

        announced = []
        for index, amount in enumerate(["5000", "5000", "10000", "60000", "100000"]):
            outcome = pay(account, amount, ref=f"ref-{index}")
            assert isinstance(outcome, PaymentApplied)
            announced.extend(outcome.events)

        assert announced == [AcceptanceFeePaid(applicant_id=APPLICANT_ID)]
        assert account.acceptance_fee_settled

    def test_a_replay_of_the_settling_payment_produces_nothing(self) -> None:
        """The event and the idempotency invariant meeting: this is the replay that would
        double-announce if the reference were not the guard."""
        account = an_admitted_account()
        pay(account, "20000", ref="ref-1")
        replay = pay(account, "20000", ref="ref-1", when=SEPTEMBER)
        assert isinstance(replay, DuplicatePaymentIgnored)
        assert replay.events == ()

    def test_an_overpayment_that_settles_the_acceptance_fee_announces_it_once(self) -> None:
        account = an_admitted_account()
        outcome = pay(account, "500000", ref="ref-1")
        assert isinstance(outcome, PaymentApplied)
        assert outcome.events == (AcceptanceFeePaid(applicant_id=APPLICANT_ID),)

    def test_settling_the_matriculation_fee_announces_nothing(self) -> None:
        """CLAUDE.md section 4: the matriculation fee gates nothing."""
        account = Account.open(APPLICANT_ID, PROGRAM_ID)
        account.raise_matriculation_fee(SESSION_ID, MATRICULATION_FEE)
        outcome = pay(account, "50000", ref="ref-1")
        assert isinstance(outcome, PaymentApplied)
        assert outcome.events == ()

    def test_settling_a_session_fee_announces_nothing(self) -> None:
        account = Account.open(APPLICANT_ID, PROGRAM_ID)
        account.raise_session_fee(SESSION_ID, SESSION_FEE)
        outcome = pay(account, "100000", ref="ref-1")
        assert isinstance(outcome, PaymentApplied)
        assert outcome.events == ()

    def test_an_account_with_no_acceptance_charge_is_not_settled(self) -> None:
        """``False`` while none has been raised — not vacuously true."""
        assert not an_account().acceptance_fee_settled


class TestLinkingTheMatricNumber:
    def test_linking_gives_the_ledger_a_second_name(self) -> None:
        account = an_admitted_account()
        assert account.link_student_id(MATRIC_NUMBER)
        assert account.student_id == MATRIC_NUMBER
        assert account.party_ids == frozenset({APPLICANT_ID, MATRIC_NUMBER})

    def test_the_ledger_continues_rather_than_starting_again(self) -> None:
        account = an_admitted_account()
        pay(account, "20000", ref="ref-1")
        account.link_student_id(MATRIC_NUMBER)
        assert account.total_paid == naira("20000")
        assert account.outstanding == naira("50000")

    def test_linking_the_same_number_again_is_a_no_op(self) -> None:
        account = an_admitted_account()
        account.link_student_id(MATRIC_NUMBER)
        assert account.link_student_id(MATRIC_NUMBER) is False

    def test_refuses_a_second_different_number(self) -> None:
        """One ledger answering to two people leaves nobody able to say whose money was whose."""
        account = an_admitted_account()
        account.link_student_id(MATRIC_NUMBER)
        with pytest.raises(PartyAlreadyLinkedError):
            account.link_student_id("260591002")

    def test_refuses_a_blank_number(self) -> None:
        with pytest.raises(MissingIdentifierError):
            an_admitted_account().link_student_id("  ")
