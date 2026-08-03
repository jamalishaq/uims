"""``ReadAccount``: the statement, and the two figures Phase 5.2 will build a rule out of.

What is under test as much as the numbers is what the statement *is not*: a way to change a
ledger, and an answer to "is this student cleared". The first would make a read path a write
path; the second would move a rule out from behind ``FinancialClearancePort``, where CLAUDE.md
section 3 puts it.
"""

from datetime import datetime

import pytest

from billing.application import AccountNotFoundError, ReadAccount
from billing.domain import Account, ChargeKind, Money
from billing.ports import AccountRepositoryPort

APPLICANT_ID = "app-0001"
PROGRAM_ID = "prog-csc-bsc"
SESSION_2026 = "sess-2026"
AUGUST = datetime(2026, 8, 1, 9, 30)


@pytest.fixture
async def a_part_paid_account(accounts: AccountRepositoryPort) -> Account:
    account = Account.open(APPLICANT_ID, PROGRAM_ID)
    account.raise_acceptance_fee(SESSION_2026, Money("20000"))
    account.raise_session_fee(SESSION_2026, Money("100000"))
    account.apply_payment(gateway_ref="ref-1", amount=Money("90000"), received_at=AUGUST)
    await accounts.add(account)
    return account


async def test_states_what_was_charged_what_was_paid_and_what_is_left(
    read_account: ReadAccount, a_part_paid_account: Account
) -> None:
    statement = await read_account.execute(APPLICANT_ID)

    assert statement.total_charged == Money("120000")
    assert statement.total_paid == Money("90000")
    assert statement.outstanding == Money("30000")
    assert statement.credit_balance == Money.zero()
    assert statement.acceptance_fee_settled


async def test_gives_the_clearance_adapter_the_session_fee_and_how_much_of_it_is_met(
    read_account: ReadAccount, a_part_paid_account: Account
) -> None:
    """The two figures 70% and 100% will be computed from — over there, in the adapter."""
    statement = await read_account.execute(APPLICANT_ID)

    session_fee = statement.charge_for(ChargeKind.SESSION, SESSION_2026)
    assert session_fee is not None
    assert session_fee.amount == Money("100000")
    assert session_fee.allocated == Money("70000")


async def test_says_nothing_about_whether_anybody_is_cleared(
    read_account: ReadAccount, a_part_paid_account: Account
) -> None:
    """No percentage, no threshold, no verdict: that rule lives behind
    ``FinancialClearancePort`` and nowhere else."""
    statement = await read_account.execute(APPLICANT_ID)
    fields = set(vars(statement))
    assert not {field for field in fields if "clear" in field or "percent" in field}


async def test_the_statement_cannot_be_written_through(
    read_account: ReadAccount, a_part_paid_account: Account
) -> None:
    """A DTO and not the aggregate: no ``apply_payment`` came with it."""
    statement = await read_account.execute(APPLICANT_ID)
    assert not hasattr(statement, "apply_payment")
    assert not hasattr(statement, "raise_charge")


async def test_finding_a_party_with_no_ledger_answers_none(read_account: ReadAccount) -> None:
    """The form a port adapter wants: a clearance check about somebody unknown has an answer."""
    assert await read_account.find("app-9999") is None


async def test_reading_a_party_with_no_ledger_is_an_error(read_account: ReadAccount) -> None:
    with pytest.raises(AccountNotFoundError):
        await read_account.execute("app-9999")
