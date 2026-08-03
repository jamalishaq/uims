"""The in-memory adapters behind Billing's three ports.

Mostly the same add/save/get contract every context's store carries. The part worth reading is
the alias index: an account is stored under the id it was opened with and answers to the matric
number it is later linked to, which is the party-id abstraction actually costing something.
"""

import pytest

from billing.adapters.outbound import (
    InMemoryAccountRepository,
    InMemoryEventPublisher,
    InMemoryFeeScheduleRepository,
)
from billing.domain import AcceptanceFeePaid, Account, FeeSchedule, Money
from billing.ports import AggregateNotFoundError, DuplicateAggregateError

APPLICANT_ID = "app-0001"
MATRIC_NUMBER = "260591001"
PROGRAM_ID = "prog-csc-bsc"
SESSION_2026 = "sess-2026"


def an_account(party_id: str = APPLICANT_ID) -> Account:
    return Account.open(party_id, PROGRAM_ID)


def a_schedule(session_id: str = SESSION_2026) -> FeeSchedule:
    return FeeSchedule.for_session(
        session_id, acceptance_fee=Money("20000"), matriculation_fee=Money("50000")
    )


class TestAccountRepository:
    async def test_stores_and_returns_an_account_by_its_party_id(self) -> None:
        accounts = InMemoryAccountRepository()
        account = an_account()
        await accounts.add(account)
        assert await accounts.get(APPLICANT_ID) is account

    async def test_answers_none_for_a_party_it_has_never_heard_of(self) -> None:
        assert await InMemoryAccountRepository().get("app-9999") is None

    async def test_refuses_a_second_account_for_the_same_party(self) -> None:
        accounts = InMemoryAccountRepository()
        await accounts.add(an_account())
        with pytest.raises(DuplicateAggregateError):
            await accounts.add(an_account())

    async def test_refuses_to_save_an_account_that_was_never_added(self) -> None:
        with pytest.raises(AggregateNotFoundError):
            await InMemoryAccountRepository().save(an_account())

    async def test_a_linked_account_is_reachable_by_either_id(self) -> None:
        accounts = InMemoryAccountRepository()
        account = an_account()
        await accounts.add(account)

        account.link_student_id(MATRIC_NUMBER)
        await accounts.save(account)

        assert await accounts.get(MATRIC_NUMBER) is account
        assert await accounts.get(APPLICANT_ID) is account

    async def test_the_alias_appears_only_once_the_link_is_saved(self) -> None:
        """The index is rebuilt on write, which is what a unique index on a column would be."""
        accounts = InMemoryAccountRepository()
        account = an_account()
        await accounts.add(account)

        account.link_student_id(MATRIC_NUMBER)

        assert await accounts.get(MATRIC_NUMBER) is None

    async def test_lists_every_account_in_the_order_opened(self) -> None:
        accounts = InMemoryAccountRepository()
        await accounts.add(an_account("app-0001"))
        await accounts.add(an_account("app-0002"))
        assert [account.party_id for account in await accounts.all_active()] == [
            "app-0001",
            "app-0002",
        ]

    async def test_lists_nothing_when_nobody_has_accepted_an_offer(self) -> None:
        assert await InMemoryAccountRepository().all_active() == ()


class TestFeeScheduleRepository:
    async def test_stores_and_returns_a_schedule_by_its_session(self) -> None:
        schedules = InMemoryFeeScheduleRepository()
        schedule = a_schedule()
        await schedules.add(schedule)
        assert await schedules.get(SESSION_2026) is schedule

    async def test_answers_none_for_an_unpublished_session(self) -> None:
        assert await InMemoryFeeScheduleRepository().get(SESSION_2026) is None

    async def test_refuses_a_second_schedule_for_the_same_session(self) -> None:
        schedules = InMemoryFeeScheduleRepository()
        await schedules.add(a_schedule())
        with pytest.raises(DuplicateAggregateError):
            await schedules.add(a_schedule())

    async def test_last_session_s_schedule_survives_this_session_s(self) -> None:
        """An account charged in 2026 was charged against the 2026 schedule."""
        schedules = InMemoryFeeScheduleRepository()
        await schedules.add(a_schedule("sess-2026"))
        await schedules.add(a_schedule("sess-2027"))
        assert len(schedules.all()) == 2
        assert await schedules.get("sess-2026") is not None

    async def test_refuses_to_save_a_schedule_that_was_never_published(self) -> None:
        with pytest.raises(AggregateNotFoundError):
            await InMemoryFeeScheduleRepository().save(a_schedule())


class TestEventPublisher:
    async def test_remembers_what_was_published_in_order(self) -> None:
        publisher = InMemoryEventPublisher()
        await publisher.publish(AcceptanceFeePaid(applicant_id="app-0001"))
        await publisher.publish(AcceptanceFeePaid(applicant_id="app-0002"))
        assert publisher.published == (
            AcceptanceFeePaid(applicant_id="app-0001"),
            AcceptanceFeePaid(applicant_id="app-0002"),
        )

    async def test_keeps_a_repeat_it_should_never_have_been_given(self) -> None:
        """Which is what makes "exactly once per applicant" a claim a test can falsify."""
        publisher = InMemoryEventPublisher()
        await publisher.publish(AcceptanceFeePaid(applicant_id="app-0001"))
        await publisher.publish(AcceptanceFeePaid(applicant_id="app-0001"))
        assert len(publisher.published) == 2

    async def test_history_cannot_be_rewritten_by_a_caller(self) -> None:
        publisher = InMemoryEventPublisher()
        await publisher.publish(AcceptanceFeePaid(applicant_id="app-0001"))
        assert isinstance(publisher.published, tuple)

    async def test_can_be_cleared_between_scenarios(self) -> None:
        publisher = InMemoryEventPublisher()
        await publisher.publish(AcceptanceFeePaid(applicant_id="app-0001"))
        publisher.clear()
        assert publisher.published == ()
