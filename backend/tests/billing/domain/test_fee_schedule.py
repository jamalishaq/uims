"""``FeeSchedule``: what a session costs, and what it means when it does not say.

The amounts in this module are test fixtures and nothing else. Real fees are set by the
university (CLAUDE.md section 6), and the fact that no number in ``src/billing`` is a fee is
the property worth keeping.

The interesting case is the missing line. ``session_fee_for`` answering ``None`` is what makes
an unpriced program a *skip* in the batch rather than a failure, on the argument Admissions
makes about a missing alternative-program policy — and it is answered here rather than decided
by whoever asks.
"""

from decimal import Decimal

import pytest

from billing.domain import (
    FeeSchedule,
    InvalidFeeScheduleError,
    Level,
    MissingIdentifierError,
    Money,
    SessionFeeLine,
)

SESSION_ID = "sess-2026"
CSC = "prog-csc-bsc"
MCB = "prog-mcb-bsc"

ACCEPTANCE = Money(Decimal("20000"))
MATRICULATION = Money(Decimal("50000"))


def a_schedule(**overrides: object) -> FeeSchedule:
    fields: dict[str, object] = {
        "acceptance_fee": ACCEPTANCE,
        "matriculation_fee": MATRICULATION,
        "session_fees": (
            SessionFeeLine(program_id=CSC, level=Level(100), amount=Money(Decimal("100000"))),
            SessionFeeLine(program_id=CSC, level=Level(200), amount=Money(Decimal("90000"))),
        ),
    }
    fields.update(overrides)
    return FeeSchedule.for_session(SESSION_ID, **fields)  # type: ignore[arg-type]


class TestAdmissionFees:
    def test_carries_both_admission_fees_for_the_session(self) -> None:
        schedule = a_schedule()
        assert schedule.acceptance_fee == ACCEPTANCE
        assert schedule.matriculation_fee == MATRICULATION

    @pytest.mark.parametrize("field", ["acceptance_fee", "matriculation_fee"])
    def test_refuses_an_admission_fee_of_zero(self, field: str) -> None:
        """A gating charge that demands nothing would settle itself the moment it was raised."""
        with pytest.raises(InvalidFeeScheduleError):
            a_schedule(**{field: Money.zero()})

    @pytest.mark.parametrize("field", ["acceptance_fee", "matriculation_fee"])
    def test_refuses_an_admission_fee_that_is_not_money(self, field: str) -> None:
        with pytest.raises(InvalidFeeScheduleError):
            a_schedule(**{field: Decimal("20000")})

    def test_refuses_a_blank_session(self) -> None:
        with pytest.raises(MissingIdentifierError):
            FeeSchedule.for_session(
                "  ", acceptance_fee=ACCEPTANCE, matriculation_fee=MATRICULATION
            )


class TestSessionFees:
    def test_prices_a_program_at_a_level(self) -> None:
        assert a_schedule().session_fee_for(CSC, Level(100)) == Money(Decimal("100000"))

    def test_the_same_program_costs_differently_at_a_different_level(self) -> None:
        """Why the key is the pair and not the program alone."""
        schedule = a_schedule()
        assert schedule.session_fee_for(CSC, Level(200)) == Money(Decimal("90000"))

    def test_answers_none_for_a_combination_it_does_not_price(self) -> None:
        """``None`` is an answer, not a failure: the batch skips such an account."""
        schedule = a_schedule()
        assert schedule.session_fee_for(MCB, Level(100)) is None
        assert schedule.session_fee_for(CSC, Level(500)) is None

    def test_a_schedule_may_price_nothing_at_all(self) -> None:
        """The admission fees are what an offer needs; the rest can be published later."""
        schedule = a_schedule(session_fees=())
        assert schedule.session_fee_lines == ()
        assert schedule.session_fee_for(CSC, Level(100)) is None

    def test_refuses_the_same_program_and_level_priced_twice(self) -> None:
        """Whichever amount the code picked, half a cohort would be billed the wrong one."""
        with pytest.raises(InvalidFeeScheduleError):
            a_schedule(
                session_fees=(
                    SessionFeeLine(program_id=CSC, level=Level(100), amount=Money(Decimal("1"))),
                    SessionFeeLine(program_id=CSC, level=Level(100), amount=Money(Decimal("2"))),
                )
            )

    def test_refuses_lines_that_are_not_lines(self) -> None:
        with pytest.raises(InvalidFeeScheduleError):
            a_schedule(session_fees=((CSC, Level(100), Money(Decimal("1"))),))

    def test_refuses_a_line_priced_at_nothing(self) -> None:
        """A program that charges no session fee is left off, not priced at zero."""
        with pytest.raises(InvalidFeeScheduleError):
            SessionFeeLine(program_id=CSC, level=Level(100), amount=Money.zero())

    def test_refuses_a_level_that_is_not_one(self) -> None:
        with pytest.raises(InvalidFeeScheduleError):
            a_schedule().session_fee_for(CSC, 100)  # type: ignore[arg-type]

    def test_lines_are_readable_and_cannot_be_added_to(self) -> None:
        assert len(a_schedule().session_fee_lines) == 2
        assert isinstance(a_schedule().session_fee_lines, tuple)
