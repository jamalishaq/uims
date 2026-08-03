"""``Money``: the three things a ledger's amount type must never do.

Take a float, go negative, or round somebody's kobo away without being asked. Each of the
three is a bug that shows up as a reconciliation difference weeks later, against a payment
gateway that is definitely not wrong, and each is unrepresentable here rather than caught by a
check somewhere upstream.
"""

from decimal import Decimal

import pytest

from billing.domain import InvalidAmountError, Money


class TestConstruction:
    def test_holds_an_exact_decimal_amount(self) -> None:
        assert Money(Decimal("1500.50")).amount == Decimal("1500.50")

    @pytest.mark.parametrize("value", [Decimal("20000"), 20000, "20000", "20000.00"])
    def test_accepts_a_decimal_an_int_or_a_string(self, value: object) -> None:
        assert Money(value) == Money(Decimal("20000"))  # type: ignore[arg-type]

    def test_refuses_a_float_outright(self) -> None:
        """By the time a float arrives the precision is already gone; converting hides it."""
        with pytest.raises(InvalidAmountError):
            Money(1500.50)  # type: ignore[arg-type]

    def test_refuses_a_negative_amount(self) -> None:
        """A credit balance is a positive figure on the account, never a negative charge."""
        with pytest.raises(InvalidAmountError):
            Money(Decimal("-1"))

    def test_refuses_more_precision_than_kobo(self) -> None:
        """Rounding 0.005 away silently is how a ledger stops adding up."""
        with pytest.raises(InvalidAmountError):
            Money(Decimal("100.005"))

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
    def test_refuses_amounts_that_are_not_finite(self, value: str) -> None:
        with pytest.raises(InvalidAmountError):
            Money(Decimal(value))

    @pytest.mark.parametrize("value", [True, None, object()])
    def test_refuses_things_that_are_not_amounts(self, value: object) -> None:
        with pytest.raises(InvalidAmountError):
            Money(value)  # type: ignore[arg-type]

    def test_refuses_a_string_that_is_not_a_number(self) -> None:
        with pytest.raises(InvalidAmountError):
            Money("twenty thousand")

    def test_normalises_to_two_places_so_equal_amounts_compare_equal(self) -> None:
        assert Money(Decimal("100")) == Money(Decimal("100.00"))
        assert hash(Money(Decimal("100"))) == hash(Money(Decimal("100.00")))

    def test_zero_is_zero(self) -> None:
        assert Money.zero().is_zero
        assert not Money(Decimal("0.01")).is_zero


class TestArithmetic:
    def test_adds(self) -> None:
        assert Money(Decimal("100.25")) + Money(Decimal("0.75")) == Money(Decimal("101.00"))

    def test_subtracts(self) -> None:
        assert Money(Decimal("100")) - Money(Decimal("40.50")) == Money(Decimal("59.50"))

    def test_refuses_a_subtraction_that_would_go_below_zero(self) -> None:
        """A caller whose arithmetic is wrong finds out here, not in a total three layers up."""
        with pytest.raises(InvalidAmountError):
            Money(Decimal("40")) - Money(Decimal("100"))

    def test_adding_repeatedly_does_not_drift(self) -> None:
        """The float test. A tenth of a naira, ten thousand times, is exactly a thousand."""
        total = Money.zero()
        for _ in range(10_000):
            total = total + Money(Decimal("0.10"))
        assert total == Money(Decimal("1000.00"))

    def test_orders_so_the_smaller_of_two_amounts_can_be_taken(self) -> None:
        """What allocation does: take the lesser of what is available and what is owed."""
        assert min(Money(Decimal("100")), Money(Decimal("40"))) == Money(Decimal("40"))
        assert Money(Decimal("40")) < Money(Decimal("100"))

    def test_reads_as_an_amount(self) -> None:
        assert str(Money(Decimal("1500.5"))) == "1500.50"
