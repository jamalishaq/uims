"""The clearance rule at its boundaries: 69/70/71% for first semester, 99/100% for second.

The build playbook's verification for Phase 5.2, written where the rule lives. Billing appears
nowhere in this module — the adapter is fed a dictionary — so a failure here is a failure of the
*rule* and not of a ledger, an allocation order or a fee schedule. That the same numbers come
out when the figures are computed by a real ``Account`` is
``tests/enrollment/test_billing_clearance_wiring.py``'s job.

The fee is 100,000 so that a percentage and an amount are the same number times a thousand and a
reader can check the arithmetic in their head. It is a test fixture and not an institutional
fact: real fees arrive on a published ``FeeSchedule`` (CLAUDE.md section 6), and nothing in
``src/`` contains an amount.
"""

from decimal import Decimal

import pytest

from enrollment.adapters.outbound import (
    BILLING_CLEARANCE_THRESHOLDS,
    BillingFinancialClearanceAdapter,
    ClearanceThresholds,
    MalformedSessionFeeError,
    SessionFeePosition,
)
from enrollment.domain import SemesterOrdinal, Term

STUDENT_ID = "stu-260591001"
SESSION_ID = "sess-2026"
SESSION_FEE = Decimal("100000.00")

FIRST = Term(session_id=SESSION_ID, semester_id="sem-2026-1", ordinal=SemesterOrdinal.FIRST)
SECOND = Term(session_id=SESSION_ID, semester_id="sem-2026-2", ordinal=SemesterOrdinal.SECOND)


class FakeSessionFeeLedger:
    """Whatever the other side of the port would say, stated outright.

    Satisfies ``SessionFeeLedger`` structurally, which is the point of that Protocol: the class
    answering it in production lives outside this context and cannot inherit from anything in
    it.
    """

    def __init__(self) -> None:
        self._positions: dict[tuple[str, str], SessionFeePosition] = {}
        self.asked: list[tuple[str, str]] = []

    def record(
        self, party_id: str, session_id: str, charged: Decimal, settled: Decimal
    ) -> "FakeSessionFeeLedger":
        self._positions[(party_id, session_id)] = SessionFeePosition(
            charged=charged, settled=settled
        )
        return self

    def session_fee_for(self, party_id: str, session_id: str) -> SessionFeePosition | None:
        self.asked.append((party_id, session_id))
        return self._positions.get((party_id, session_id))


def an_adapter(
    settled: Decimal | None = None,
    *,
    charged: Decimal = SESSION_FEE,
    thresholds: ClearanceThresholds = BILLING_CLEARANCE_THRESHOLDS,
) -> BillingFinancialClearanceAdapter:
    """An adapter over a ledger holding one student's position, or over an empty one."""
    ledger = FakeSessionFeeLedger()
    if settled is not None:
        ledger.record(STUDENT_ID, SESSION_ID, charged=charged, settled=settled)
    return BillingFinancialClearanceAdapter(ledger, thresholds)


class TestFirstSemesterNeedsSeventyPercent:
    @pytest.mark.parametrize(
        ("settled", "cleared"),
        [
            (Decimal("69000.00"), False),
            (Decimal("70000.00"), True),
            (Decimal("71000.00"), True),
        ],
        ids=["69%", "70%", "71%"],
    )
    def test_the_boundary_is_at_seventy(self, settled: Decimal, cleared: bool) -> None:
        """Seventy exactly is enough: the confirmed rule is *at least* 70% (CLAUDE.md 3)."""
        assert an_adapter(settled).is_cleared_for_registration(STUDENT_ID, FIRST) is cleared

    def test_nothing_paid_is_refused(self) -> None:
        assert an_adapter(Decimal("0.00")).is_cleared_for_registration(STUDENT_ID, FIRST) is False

    def test_the_whole_fee_clears_first_semester_too(self) -> None:
        """The 30% may be deferred, not must be."""
        assert an_adapter(SESSION_FEE).is_cleared_for_registration(STUDENT_ID, FIRST) is True


class TestSecondSemesterNeedsAllOfIt:
    @pytest.mark.parametrize(
        ("settled", "cleared"),
        [
            (Decimal("99000.00"), False),
            (Decimal("100000.00"), True),
        ],
        ids=["99%", "100%"],
    )
    def test_the_boundary_is_at_a_hundred(self, settled: Decimal, cleared: bool) -> None:
        """The deferred 30% falls due here; a kobo short is short."""
        assert an_adapter(settled).is_cleared_for_registration(STUDENT_ID, SECOND) is cleared

    def test_a_single_kobo_outstanding_refuses(self) -> None:
        settled = SESSION_FEE - Decimal("0.01")
        assert an_adapter(settled).is_cleared_for_registration(STUDENT_ID, SECOND) is False


class TestTheTwoHalvesDisagree:
    """The same ledger, two answers. This difference is the whole reason the port takes a term."""

    @pytest.mark.parametrize(
        ("settled", "first", "second"),
        [
            (Decimal("69000.00"), False, False),
            (Decimal("70000.00"), True, False),
            (Decimal("99000.00"), True, False),
            (Decimal("100000.00"), True, True),
        ],
        ids=["69%", "70%", "99%", "100%"],
    )
    def test_first_semester_clears_where_second_refuses(
        self, settled: Decimal, first: bool, second: bool
    ) -> None:
        adapter = an_adapter(settled)
        assert adapter.is_cleared_for_registration(STUDENT_ID, FIRST) is first
        assert adapter.is_cleared_for_registration(STUDENT_ID, SECOND) is second


class TestTheComparisonIsExact:
    def test_a_fee_that_does_not_divide_is_not_rounded_into_clearance(self) -> None:
        """70% of 100,000.01 is 70,000.007 — payable only by rounding, which is not paying.

        An implementation dividing and quantizing to kobo would read this as exactly 70% and
        clear the student. Cross-multiplying refuses it, which is the correct answer and the
        reason the adapter's docstring says not to simplify the comparison.
        """
        adapter = an_adapter(Decimal("70000.00"), charged=Decimal("100000.01"))
        assert adapter.is_cleared_for_registration(STUDENT_ID, FIRST) is False

    def test_a_kobo_more_clears_it(self) -> None:
        adapter = an_adapter(Decimal("70000.01"), charged=Decimal("100000.01"))
        assert adapter.is_cleared_for_registration(STUDENT_ID, FIRST) is True


class TestNothingOnRecordIsRefused:
    """Three different absences, one answer, decided with the user rather than inferred."""

    def test_a_party_with_no_ledger_is_not_cleared(self) -> None:
        assert an_adapter().is_cleared_for_registration(STUDENT_ID, FIRST) is False

    def test_a_ledger_without_this_session_is_not_cleared(self) -> None:
        """A fee paid in full for last session says nothing about this one."""
        ledger = FakeSessionFeeLedger().record(
            STUDENT_ID, "sess-2025", charged=SESSION_FEE, settled=SESSION_FEE
        )
        adapter = BillingFinancialClearanceAdapter(ledger)
        assert adapter.is_cleared_for_registration(STUDENT_ID, FIRST) is False

    def test_somebody_elses_settled_fee_does_not_clear_this_student(self) -> None:
        ledger = FakeSessionFeeLedger().record(
            "stu-260591002", SESSION_ID, charged=SESSION_FEE, settled=SESSION_FEE
        )
        adapter = BillingFinancialClearanceAdapter(ledger)
        assert adapter.is_cleared_for_registration(STUDENT_ID, FIRST) is False

    def test_the_answer_is_a_bool_and_not_something_bool_shaped(self) -> None:
        """The port promises a boolean; a caller may not be handed a truthy Decimal."""
        answer = an_adapter(SESSION_FEE).is_cleared_for_registration(STUDENT_ID, FIRST)
        assert isinstance(answer, bool)


class TestWhatTheLedgerIsAsked:
    def test_it_is_asked_for_the_session_never_the_semester(self) -> None:
        """A fee is charged per session. Asking per semester would demand two bills."""
        ledger = FakeSessionFeeLedger()
        adapter = BillingFinancialClearanceAdapter(ledger)
        adapter.is_cleared_for_registration(STUDENT_ID, SECOND)
        assert ledger.asked == [(STUDENT_ID, SESSION_ID)]

    def test_the_student_id_crosses_as_the_party_id_untranslated(self) -> None:
        """Billing resolves either id to one ledger, so a matric number is a party-id there."""
        ledger = FakeSessionFeeLedger()
        BillingFinancialClearanceAdapter(ledger).is_cleared_for_registration("260591001", FIRST)
        assert ledger.asked == [("260591001", SESSION_ID)]


class TestThePercentagesAreAConstructionArgument:
    """If the university changes the rule, one construction argument changes and no code does."""

    @pytest.mark.parametrize(
        ("settled", "first", "second"),
        [
            (Decimal("49000.00"), False, False),
            (Decimal("50000.00"), True, False),
            (Decimal("80000.00"), True, True),
        ],
        ids=["49%", "50%", "80%"],
    )
    def test_a_fifty_eighty_rule_moves_both_boundaries(
        self, settled: Decimal, first: bool, second: bool
    ) -> None:
        adapter = an_adapter(settled, thresholds=ClearanceThresholds(Decimal("50"), Decimal("80")))
        assert adapter.is_cleared_for_registration(STUDENT_ID, FIRST) is first
        assert adapter.is_cleared_for_registration(STUDENT_ID, SECOND) is second

    def test_the_confirmed_rule_is_the_default(self) -> None:
        assert BILLING_CLEARANCE_THRESHOLDS.first_semester_percent == Decimal("70")
        assert BILLING_CLEARANCE_THRESHOLDS.second_semester_percent == Decimal("100")

    def test_required_percent_reads_the_term_and_not_the_semester_id(self) -> None:
        odd = Term(session_id=SESSION_ID, semester_id="sem-2026-1", ordinal=SemesterOrdinal.SECOND)
        assert BILLING_CLEARANCE_THRESHOLDS.required_percent(odd) == Decimal("100")

    @pytest.mark.parametrize("percent", [Decimal("-1"), Decimal("101"), 70, 0.7])
    def test_a_threshold_that_is_not_a_percentage_is_refused(self, percent: object) -> None:
        with pytest.raises(MalformedSessionFeeError):
            ClearanceThresholds(percent, Decimal("100"))  # type: ignore[arg-type]


class TestSessionFeePositionRefusesNonsense:
    """A translation that misread Billing fails at the boundary, not as a quiet 'not cleared'."""

    @pytest.mark.parametrize("charged", [100000.0, "100000", 100000])
    def test_a_figure_that_is_not_a_decimal_is_refused(self, charged: object) -> None:
        with pytest.raises(MalformedSessionFeeError):
            SessionFeePosition(charged=charged, settled=Decimal("0"))  # type: ignore[arg-type]

    def test_a_fee_of_nothing_is_refused(self) -> None:
        """No session fee is reported as absent, never as a charge of zero."""
        with pytest.raises(MalformedSessionFeeError):
            SessionFeePosition(charged=Decimal("0"), settled=Decimal("0"))

    def test_a_negative_fee_is_refused(self) -> None:
        with pytest.raises(MalformedSessionFeeError):
            SessionFeePosition(charged=Decimal("-1"), settled=Decimal("0"))

    def test_settling_more_than_was_charged_is_refused(self) -> None:
        """Billing's own ``Charge`` forbids it; a translation producing it has misread one."""
        with pytest.raises(MalformedSessionFeeError):
            SessionFeePosition(charged=SESSION_FEE, settled=SESSION_FEE + Decimal("0.01"))
