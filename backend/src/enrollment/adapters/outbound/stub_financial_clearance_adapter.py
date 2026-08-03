"""The fake behind ``FinancialClearancePort``: a clearance answer stated rather than computed.

**Written as a stand-in, kept as a fake.** Until Phase 5.2 this was the only implementation of
the port, standing in for a Billing context that did not exist. It now sits beside the real one,
``BillingFinancialClearanceAdapter``, and does the job ``InMemoryCourseInfoAdapter`` does for
Course Catalog: it lets a test say what the other context would answer, in one line, without
standing a ledger up. That the swap could
be made without touching a line of ``domain/``, ``ports/``, ``application/`` or a single
application test is the requirement the build playbook set for Phase 5.2, and keeping this
class is what met it.

It answers cleared for everyone by default, because a test about prerequisites or credit load
should not have to pay a session fee to get to the assertion it cares about. ``deny`` is how
the refusal path gets exercised, per student and per term.

There is no rule in here and there must not be one. The percentages, the fee and the arithmetic
live in the real adapter; what this class establishes is the shape they stop at — a boolean
crosses, and nothing else.
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
