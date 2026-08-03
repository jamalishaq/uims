"""``LinkStudentAccount``: the ledger gains a second name at matriculation.

Nothing drives this yet — no event in the system carries a matric number — so what is under
test is the use case an administrative interface calls, and the property that matters is that
linking *continues* a ledger rather than starting one.
"""

import pytest

from billing.application import (
    AccountNotFoundError,
    LinkStudentAccount,
    LinkStudentAccountCommand,
)
from billing.domain import Account, Money, PartyAlreadyLinkedError
from billing.ports import AccountRepositoryPort

APPLICANT_ID = "app-0001"
MATRIC_NUMBER = "260591001"
PROGRAM_ID = "prog-csc-bsc"
SESSION_2026 = "sess-2026"


@pytest.fixture
async def an_account(accounts: AccountRepositoryPort) -> Account:
    account = Account.open(APPLICANT_ID, PROGRAM_ID)
    account.raise_acceptance_fee(SESSION_2026, Money("20000"))
    await accounts.add(account)
    return account


async def test_linking_makes_the_ledger_reachable_by_the_matric_number(
    link_student_account: LinkStudentAccount,
    accounts: AccountRepositoryPort,
    an_account: Account,
) -> None:
    result = await link_student_account.execute(
        LinkStudentAccountCommand(party_id=APPLICANT_ID, student_id=MATRIC_NUMBER)
    )

    assert result.was_already_linked is False
    assert await accounts.get(MATRIC_NUMBER) is an_account
    assert await accounts.get(APPLICANT_ID) is an_account


async def test_the_ledger_continues_rather_than_starting_again(
    link_student_account: LinkStudentAccount, an_account: Account
) -> None:
    """CLAUDE.md section 3: one continuous ledger from the acceptance fee onward."""
    await link_student_account.execute(
        LinkStudentAccountCommand(party_id=APPLICANT_ID, student_id=MATRIC_NUMBER)
    )
    assert an_account.outstanding == Money("20000")
    assert len(an_account.charges) == 1


async def test_linking_the_same_number_again_is_a_no_op(
    link_student_account: LinkStudentAccount, an_account: Account
) -> None:
    command = LinkStudentAccountCommand(party_id=APPLICANT_ID, student_id=MATRIC_NUMBER)
    await link_student_account.execute(command)

    result = await link_student_account.execute(command)

    assert result.was_already_linked is True


async def test_linking_works_when_the_matric_number_is_the_id_quoted(
    link_student_account: LinkStudentAccount, an_account: Account
) -> None:
    """A caller holding either id reaches the ledger, which is the point of the party-id."""
    await link_student_account.execute(
        LinkStudentAccountCommand(party_id=APPLICANT_ID, student_id=MATRIC_NUMBER)
    )

    result = await link_student_account.execute(
        LinkStudentAccountCommand(party_id=MATRIC_NUMBER, student_id=MATRIC_NUMBER)
    )

    assert result.was_already_linked is True


async def test_a_second_different_number_is_refused(
    link_student_account: LinkStudentAccount, an_account: Account
) -> None:
    await link_student_account.execute(
        LinkStudentAccountCommand(party_id=APPLICANT_ID, student_id=MATRIC_NUMBER)
    )

    with pytest.raises(PartyAlreadyLinkedError):
        await link_student_account.execute(
            LinkStudentAccountCommand(party_id=APPLICANT_ID, student_id="260591002")
        )


async def test_a_party_with_no_ledger_is_refused(link_student_account: LinkStudentAccount) -> None:
    with pytest.raises(AccountNotFoundError):
        await link_student_account.execute(
            LinkStudentAccountCommand(party_id="app-9999", student_id=MATRIC_NUMBER)
        )
