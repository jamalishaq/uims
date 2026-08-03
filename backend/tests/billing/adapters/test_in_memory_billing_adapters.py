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
    def test_stores_and_returns_an_account_by_its_party_id(self) -> None:
        accounts = InMemoryAccountRepository()
        account = an_account()
        accounts.add(account)
        assert accounts.get(APPLICANT_ID) is account

    def test_answers_none_for_a_party_it_has_never_heard_of(self) -> None:
        assert InMemoryAccountRepository().get("app-9999") is None

    def test_refuses_a_second_account_for_the_same_party(self) -> None:
        accounts = InMemoryAccountRepository()
        accounts.add(an_account())
        with pytest.raises(DuplicateAggregateError):
            accounts.add(an_account())

    def test_refuses_to_save_an_account_that_was_never_added(self) -> None:
        with pytest.raises(AggregateNotFoundError):
            InMemoryAccountRepository().save(an_account())

    def test_a_linked_account_is_reachable_by_either_id(self) -> None:
        accounts = InMemoryAccountRepository()
        account = an_account()
        accounts.add(account)

        account.link_student_id(MATRIC_NUMBER)
        accounts.save(account)

        assert accounts.get(MATRIC_NUMBER) is account
        assert accounts.get(APPLICANT_ID) is account

    def test_the_alias_appears_only_once_the_link_is_saved(self) -> None:
        """The index is rebuilt on write, which is what a unique index on a column would be."""
        accounts = InMemoryAccountRepository()
        account = an_account()
        accounts.add(account)

        account.link_student_id(MATRIC_NUMBER)

        assert accounts.get(MATRIC_NUMBER) is None

    def test_lists_every_account_in_the_order_opened(self) -> None:
        accounts = InMemoryAccountRepository()
        accounts.add(an_account("app-0001"))
        accounts.add(an_account("app-0002"))
        assert [account.party_id for account in accounts.all_active()] == ["app-0001", "app-0002"]

    def test_lists_nothing_when_nobody_has_accepted_an_offer(self) -> None:
        assert InMemoryAccountRepository().all_active() == ()


class TestFeeScheduleRepository:
    def test_stores_and_returns_a_schedule_by_its_session(self) -> None:
        schedules = InMemoryFeeScheduleRepository()
        schedule = a_schedule()
        schedules.add(schedule)
        assert schedules.get(SESSION_2026) is schedule

    def test_answers_none_for_an_unpublished_session(self) -> None:
        assert InMemoryFeeScheduleRepository().get(SESSION_2026) is None

    def test_refuses_a_second_schedule_for_the_same_session(self) -> None:
        schedules = InMemoryFeeScheduleRepository()
        schedules.add(a_schedule())
        with pytest.raises(DuplicateAggregateError):
            schedules.add(a_schedule())

    def test_last_session_s_schedule_survives_this_session_s(self) -> None:
        """An account charged in 2026 was charged against the 2026 schedule."""
        schedules = InMemoryFeeScheduleRepository()
        schedules.add(a_schedule("sess-2026"))
        schedules.add(a_schedule("sess-2027"))
        assert len(schedules.all()) == 2
        assert schedules.get("sess-2026") is not None

    def test_refuses_to_save_a_schedule_that_was_never_published(self) -> None:
        with pytest.raises(AggregateNotFoundError):
            InMemoryFeeScheduleRepository().save(a_schedule())


class TestEventPublisher:
    def test_remembers_what_was_published_in_order(self) -> None:
        publisher = InMemoryEventPublisher()
        publisher.publish(AcceptanceFeePaid(applicant_id="app-0001"))
        publisher.publish(AcceptanceFeePaid(applicant_id="app-0002"))
        assert publisher.published == (
            AcceptanceFeePaid(applicant_id="app-0001"),
            AcceptanceFeePaid(applicant_id="app-0002"),
        )

    def test_keeps_a_repeat_it_should_never_have_been_given(self) -> None:
        """Which is what makes "exactly once per applicant" a claim a test can falsify."""
        publisher = InMemoryEventPublisher()
        publisher.publish(AcceptanceFeePaid(applicant_id="app-0001"))
        publisher.publish(AcceptanceFeePaid(applicant_id="app-0001"))
        assert len(publisher.published) == 2

    def test_history_cannot_be_rewritten_by_a_caller(self) -> None:
        publisher = InMemoryEventPublisher()
        publisher.publish(AcceptanceFeePaid(applicant_id="app-0001"))
        assert isinstance(publisher.published, tuple)

    def test_can_be_cleared_between_scenarios(self) -> None:
        publisher = InMemoryEventPublisher()
        publisher.publish(AcceptanceFeePaid(applicant_id="app-0001"))
        publisher.clear()
        assert publisher.published == ()
