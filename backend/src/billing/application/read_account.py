"""Read a party's ledger: what was charged, what was paid, what is left.

The surface the rest of the university reads Billing through — and, specifically, what the
adapter behind Enrollment's ``FinancialClearancePort`` will call when Phase 5.2 replaces its
stub. That adapter needs two figures per session: what the session fee was and how much of it
has been met. :meth:`ReadAccount.find` gives it those and nothing else it could build a
different rule out of.

**The percentages are not here.** ≥70% for first-semester registration and 100% for second is
Billing policy that "lives entirely behind ``FinancialClearancePort``" (CLAUDE.md section 3),
which means in the adapter, so that changing the numbers changes one file. A statement that
answered "is this student cleared" would have moved the rule into a use case and left the port
with nothing to do but forward it.

The view is a DTO and not the aggregate. Handing out an ``Account`` would hand out
``apply_payment`` and ``raise_charge`` along with it, and a read path that can write is a read
path somebody will eventually write through — which here means a path that could put money on
a ledger without a gateway reference to account for it.
"""

from dataclasses import dataclass

from billing.application.errors import AccountNotFoundError
from billing.domain.charge import Charge, ChargeKind
from billing.domain.payment import Payment
from billing.domain.values import Level, Money
from billing.ports.account_repository import AccountRepositoryPort


@dataclass(frozen=True)
class AccountStatement:
    """Everything a reader can be told about a ledger, and nothing they can change."""

    party_id: str
    student_id: str | None
    program_id: str
    level: Level
    charges: tuple[Charge, ...]
    payments: tuple[Payment, ...]
    total_charged: Money
    total_paid: Money
    total_allocated: Money
    outstanding: Money
    credit_balance: Money
    acceptance_fee_settled: bool

    def charge_for(self, kind: ChargeKind, session_id: str) -> Charge | None:
        """The charge of one kind for one session, or ``None`` if it was never raised.

        What the clearance adapter reads: the session fee's ``amount`` and ``allocated``, from
        which a percentage is *its* to compute.
        """
        key = (kind, session_id)
        return next((charge for charge in self.charges if charge.key == key), None)


class ReadAccount:
    """Answers questions about a ledger without letting anybody change one."""

    def __init__(self, accounts: AccountRepositoryPort) -> None:
        self._accounts = accounts

    async def execute(self, party_id: str) -> AccountStatement:
        """Return the party's statement.

        Raises:
            AccountNotFoundError: no ledger exists for that party.
        """
        statement = await self.find(party_id)
        if statement is None:
            raise AccountNotFoundError(f"no billing account is stored for party {party_id!r}")
        return statement

    async def find(self, party_id: str) -> AccountStatement | None:
        """Return the party's statement, or ``None`` if they have never been charged.

        The form a *port adapter* wants, and the reason both exist: a clearance check asked
        about somebody with no ledger has an answer, and making it travel as an exception
        would put a normal question on an error path.
        """
        account = await self._accounts.get(party_id)
        if account is None:
            return None

        return AccountStatement(
            party_id=account.party_id,
            student_id=account.student_id,
            program_id=account.program_id,
            level=account.level,
            charges=account.charges,
            payments=account.payments,
            total_charged=account.total_charged,
            total_paid=account.total_paid,
            total_allocated=account.total_allocated,
            outstanding=account.outstanding,
            credit_balance=account.credit_balance,
            acceptance_fee_settled=account.acceptance_fee_settled,
        )
