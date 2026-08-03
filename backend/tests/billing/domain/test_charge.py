"""``Charge``: what is owed, what has been met, and which kind holds something up.

The distinction under test is the one CLAUDE.md states twice and section 4 lists among the
things not to do: the acceptance fee gates matriculation and the matriculation fee gates
nothing. Everything else here is a frozen value refusing to be built wrong.
"""

from decimal import Decimal

import pytest

from billing.domain import Charge, ChargeKind, InvalidChargeError, MissingIdentifierError, Money

SESSION_ID = "sess-2026"
TWENTY_THOUSAND = Money(Decimal("20000"))


def an_acceptance_charge(amount: Money = TWENTY_THOUSAND) -> Charge:
    return Charge(kind=ChargeKind.ACCEPTANCE, session_id=SESSION_ID, amount=amount)


class TestWhatEachKindMeans:
    def test_only_the_acceptance_fee_gates_anything(self) -> None:
        """CLAUDE.md section 4: do not gate matriculation on the matriculation fee."""
        assert ChargeKind.ACCEPTANCE.gates_matriculation
        assert not ChargeKind.MATRICULATION.gates_matriculation
        assert not ChargeKind.SESSION.gates_matriculation

    def test_a_charge_carries_its_kind_s_opinion(self) -> None:
        assert an_acceptance_charge().gates_matriculation


class TestConstruction:
    def test_a_new_charge_owes_all_of_itself(self) -> None:
        charge = an_acceptance_charge()
        assert charge.allocated == Money.zero()
        assert charge.outstanding == TWENTY_THOUSAND
        assert not charge.is_settled

    def test_is_keyed_by_kind_and_session(self) -> None:
        assert an_acceptance_charge().key == (ChargeKind.ACCEPTANCE, SESSION_ID)

    def test_refuses_a_charge_for_nothing(self) -> None:
        """A zero charge would settle itself the moment it was raised."""
        with pytest.raises(InvalidChargeError):
            an_acceptance_charge(Money.zero())

    def test_refuses_a_kind_that_is_not_one(self) -> None:
        with pytest.raises(InvalidChargeError):
            Charge(kind="acceptance", session_id=SESSION_ID, amount=TWENTY_THOUSAND)  # type: ignore[arg-type]

    def test_refuses_a_blank_session(self) -> None:
        with pytest.raises(MissingIdentifierError):
            Charge(kind=ChargeKind.SESSION, session_id="  ", amount=TWENTY_THOUSAND)

    def test_refuses_an_amount_that_is_not_money(self) -> None:
        with pytest.raises(InvalidChargeError):
            Charge(kind=ChargeKind.SESSION, session_id=SESSION_ID, amount=Decimal("20000"))  # type: ignore[arg-type]

    def test_refuses_more_allocated_than_is_owed(self) -> None:
        """The invariant a rebuild from a database row has to respect too."""
        with pytest.raises(InvalidChargeError):
            Charge(
                kind=ChargeKind.SESSION,
                session_id=SESSION_ID,
                amount=TWENTY_THOUSAND,
                allocated=Money(Decimal("20000.01")),
            )


class TestAbsorbing:
    def test_takes_what_it_is_owed_and_leaves_the_rest(self) -> None:
        absorbed, taken = an_acceptance_charge().absorb(Money(Decimal("50000")))
        assert taken == TWENTY_THOUSAND
        assert absorbed.is_settled

    def test_takes_all_of_a_part_payment(self) -> None:
        absorbed, taken = an_acceptance_charge().absorb(Money(Decimal("5000")))
        assert taken == Money(Decimal("5000"))
        assert absorbed.outstanding == Money(Decimal("15000"))
        assert not absorbed.is_settled

    def test_hands_back_a_new_charge_and_leaves_the_original_alone(self) -> None:
        """Frozen: a ledger entry a caller could adjust in place is one whose history lies."""
        charge = an_acceptance_charge()
        absorbed, _ = charge.absorb(TWENTY_THOUSAND)
        assert charge.allocated == Money.zero()
        assert absorbed.allocated == TWENTY_THOUSAND

    def test_a_settled_charge_takes_nothing_more(self) -> None:
        settled, _ = an_acceptance_charge().absorb(TWENTY_THOUSAND)
        again, taken = settled.absorb(Money(Decimal("5000")))
        assert taken == Money.zero()
        assert again is settled

    def test_refuses_something_that_is_not_money(self) -> None:
        with pytest.raises(InvalidChargeError):
            an_acceptance_charge().absorb(Decimal("5000"))  # type: ignore[arg-type]
