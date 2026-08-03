"""The stub behind ``FinancialClearancePort``, standing in for Billing until Phase 5.

**This file is temporary and the code above it is not.** Phase 5.2 replaces this class with
the real adapter — ≥70% of the session fee to register for first semester, 100% for second
— and the requirement stated in the build playbook is that *Enrollment code must not change
at all* when it does. That is what this stub is for: to make the port real now, so the
swap later is a swap and not a redesign. Nothing in ``domain/``, ``ports/`` or
``application/`` knows this class exists.

It answers cleared for everyone by default, which is the playbook's instruction and the
only honest thing a stub can do — Billing has no ledger yet, so nobody is *known* to be
short. The overrides exist so the refusal path can be exercised: a rule that could not be
tested failing would ship untested until Phase 5, and by then it would be load-bearing.

Not an anti-corruption layer in the way its two neighbours are, because there is nothing
yet to translate. What it does establish is the *shape* of the translation: Billing's
percentages, balances and fee schedules stop here, and a boolean crosses.
"""

from enrollment.domain.values import Term
from enrollment.ports.financial_clearance import FinancialClearancePort


class StubFinancialClearanceAdapter(FinancialClearancePort):
    """Says yes to everyone, except where a test or a fixture has said otherwise."""

    def __init__(self, *, cleared_by_default: bool = True) -> None:
        self._cleared_by_default = cleared_by_default
        self._overrides: dict[tuple[str, str, str], bool] = {}

    def deny(self, student_id: str, term: Term) -> None:
        """Record that Billing would refuse to clear this student for this term."""
        self._overrides[self._key(student_id, term)] = False

    def clear(self, student_id: str, term: Term) -> None:
        """Record that Billing would clear this student for this term."""
        self._overrides[self._key(student_id, term)] = True

    def is_cleared_for_registration(self, student_id: str, term: Term) -> bool:
        return self._overrides.get(self._key(student_id, term), self._cleared_by_default)

    @staticmethod
    def _key(student_id: str, term: Term) -> tuple[str, str, str]:
        """Per student *and* per term: clearance for first semester is not clearance for second."""
        return (student_id, term.session_id, term.semester_id)
