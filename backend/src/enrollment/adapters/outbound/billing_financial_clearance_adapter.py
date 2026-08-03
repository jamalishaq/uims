"""The real adapter behind ``FinancialClearancePort``: Billing's rule, in its one legal home.

**This is the only file in the system that knows the percentages.** CLAUDE.md section 3 states
the confirmed rule — ≥70% of the session fee to register for first semester, 100% for second,
the deferred 30% falling due in between — and puts it "entirely behind
``FinancialClearancePort``", which means here, so that changing the numbers changes one file and
no other. Enrollment asks a question and gets a yes or a no; the fee, the balance and the
arithmetic stop at this boundary. :class:`ClearanceThresholds` carries the two figures as a
value object for the same reason ``CreditLoadPolicy`` and Academic Records' ``GradingScale``
are value objects: a change of policy is a construction argument, never a second code path.

**It is fed rather than reading Billing.** No module under ``src/enrollment/`` may import
``billing`` at any layer — ``tests/architecture/test_dependency_rule.py`` rule (b), which
deliberately does not exempt imports guarded by ``if TYPE_CHECKING``. So what arrives is
:class:`SessionFeePosition`, a fact in this context's own language, handed over by whoever
stands outside both contexts: a composition root today, a client against Billing's read model
in Phase 6. The two figures it carries are exactly the two ``ReadAccount.find`` was built to
hand out, and nothing else that a different rule could be built from.

**Nothing on record is not cleared.** A party with no ledger, an account not yet linked to the
matric number it now answers to, and a ``(program_id, level)`` the fee schedule skipped all
arrive here as ``None``, and all three get a refusal. There is no session fee against which
70% can be shown to have been paid, and clearing on an absence would let a hole in the bursary's
schedule read as a settled bill. The failure is visible where it should be — the student is
refused with ``NOT_FINANCIALLY_CLEARED`` and sent to the bursary, which is the one place that
can put it right.

**The comparison cross-multiplies and never divides.** ``settled / charged`` is inexact for most
real fees, and a ratio quantized to two places would clear a student standing at 69.999% of the
session fee. Scaling both sides instead keeps the comparison exact, which is what lets the
boundary at 70% be an equality rather than an approximation. Do not simplify it into a division.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from enrollment.domain.values import Term
from enrollment.ports.financial_clearance import FinancialClearancePort

PERCENT = Decimal(100)
"""The scale both sides of the comparison are multiplied up to, so that neither is divided."""


class MalformedSessionFeeError(Exception):
    """A ledger answered with figures that cannot describe a session fee.

    Raised at the boundary rather than carried inward, on the rule that a raw failure from the
    other side of a port must never reach the application layer (CLAUDE.md section 4). A
    translation that produced a negative charge or an allocation larger than the bill has
    misread Billing, and a clearance answer computed from it would be a guess wearing a boolean.
    """


@dataclass(frozen=True)
class SessionFeePosition:
    """What Enrollment is allowed to know about a session fee: the bill, and what has met it.

    Two figures and no third. A total outstanding, a payment history or a credit balance would
    each be a number a caller could eventually compare against something, and the rule would
    have leaked out of this file — which is the whole reason ``FinancialClearancePort`` returns
    a bare boolean.

    ``Decimal`` throughout, and a ``float`` is refused rather than converted: by the time a
    float arrives the precision this comparison depends on is already gone. Billing's ``Money``
    makes the same refusal for the same reason, and this type says it again rather than
    importing it.
    """

    charged: Decimal
    settled: Decimal

    def __post_init__(self) -> None:
        for field, value in (("charged", self.charged), ("settled", self.settled)):
            if not isinstance(value, Decimal):
                raise MalformedSessionFeeError(
                    f"{field} must be a Decimal, got {type(value).__name__}; a float cannot "
                    "represent money exactly"
                )
            if not value.is_finite():
                raise MalformedSessionFeeError(f"{field} {value} is not a finite amount")
        if self.charged <= 0:
            raise MalformedSessionFeeError(
                f"a session fee of {self.charged} is a charge nobody raised; a party with no "
                "session fee is reported as absent, not as a fee of nothing"
            )
        if self.settled < 0:
            raise MalformedSessionFeeError(f"settled {self.settled} is below zero")
        if self.settled > self.charged:
            raise MalformedSessionFeeError(
                f"{self.settled} has been settled against a session fee of {self.charged}; a "
                "charge cannot absorb more than it is owed"
            )


class SessionFeeLedger(Protocol):
    """Whatever can say what a party's session fee is and how much of it has been met.

    Structural rather than an ABC, and that is the point: the class satisfying it lives outside
    this context and cannot be made to inherit from anything in here without one context
    importing the other. In Phase 6 it is a client against Billing's read model; today it is a
    handful of lines in a composition root.
    """

    async def session_fee_for(self, party_id: str, session_id: str) -> SessionFeePosition | None:
        """The party's position on that session's fee, or ``None`` if there is no such charge.

        ``None`` covers three different absences — no ledger, no link to the matric number, no
        priced fee — and deliberately does not distinguish them. Which one it was is a question
        for the bursary's own records, not for a registration decision.
        """
        ...


@dataclass(frozen=True)
class ClearanceThresholds:
    """How much of the session fee each half of the session requires, as a percentage.

    The deferral rule read the way a bursar states it: pay 70% and register, settle the rest
    before you register again. Second semester requiring 100% is what makes the remaining 30%
    fall due rather than merely be owed.
    """

    first_semester_percent: Decimal = Decimal("70")
    second_semester_percent: Decimal = Decimal("100")

    def __post_init__(self) -> None:
        for field, value in (
            ("first_semester_percent", self.first_semester_percent),
            ("second_semester_percent", self.second_semester_percent),
        ):
            if not isinstance(value, Decimal):
                raise MalformedSessionFeeError(f"{field} must be a Decimal, got {value!r}")
            if not 0 <= value <= PERCENT:
                raise MalformedSessionFeeError(
                    f"{field} of {value} is not a percentage between 0 and {PERCENT}; a charge "
                    "cannot be settled beyond its own amount, so a threshold above it would "
                    "refuse everybody forever"
                )

    def required_percent(self, term: Term) -> Decimal:
        """The share of the session fee this term demands."""
        return (
            self.first_semester_percent if term.is_first_semester else self.second_semester_percent
        )


BILLING_CLEARANCE_THRESHOLDS = ClearanceThresholds()
"""The confirmed rule (CLAUDE.md section 3). Billing policy, and a decision to change."""


class BillingFinancialClearanceAdapter(FinancialClearancePort):
    """Answers Enrollment's yes-or-no from Billing's figures, and hands over nothing else."""

    def __init__(
        self,
        ledger: SessionFeeLedger,
        thresholds: ClearanceThresholds = BILLING_CLEARANCE_THRESHOLDS,
    ) -> None:
        self._ledger = ledger
        self._thresholds = thresholds

    async def is_cleared_for_registration(self, student_id: str, term: Term) -> bool:
        """Whether enough of the term's session fee has been paid to register.

        ``student_id`` crosses as Billing's party-id without translation: that context keys one
        continuous ledger by a neutral id and resolves either the applicant id or the matric
        number to it, so a matric number is a party-id there the moment ``LinkStudentAccount``
        has run. The session is asked for, never the semester — a fee is charged per session
        and the halves differ only in how much of it is demanded.
        """
        position = await self._ledger.session_fee_for(student_id, term.session_id)
        if position is None:
            return False
        required = self._thresholds.required_percent(term)
        return position.settled * PERCENT >= position.charged * required
