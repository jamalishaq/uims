"""``ApplySessionFees``: one event, every account.

The only fan-out in this system, and the tests that matter are about what it does when it
cannot do the obvious thing. An account whose program and level the schedule does not price is
skipped and named; a session with no schedule at all stops the batch; a redelivered
``SessionOpened`` charges nobody twice.
"""

import pytest

from billing.adapters.outbound import InMemoryEventPublisher, InMemoryFeeScheduleRepository
from billing.application import ApplySessionFees, FeeScheduleNotPublishedError
from billing.domain import Account, ChargeKind, FeeSchedule, Level, Money, SessionFeeLine
from billing.ports import AccountRepositoryPort

SESSION_2026 = "sess-2026"
CSC_PROGRAM_ID = "prog-csc-bsc"
MCB_PROGRAM_ID = "prog-mcb-bsc"
LAW_PROGRAM_ID = "prog-law-llb"


@pytest.fixture
def a_cohort(accounts: AccountRepositoryPort) -> AccountRepositoryPort:
    """Three accounts: two the schedule prices, and one on a program nobody has priced."""
    accounts.add(Account.open("app-0001", CSC_PROGRAM_ID))
    accounts.add(Account.open("app-0002", MCB_PROGRAM_ID))
    accounts.add(Account.open("app-0003", LAW_PROGRAM_ID))
    return accounts


def test_charges_every_account_the_schedule_prices(
    apply_session_fees: ApplySessionFees,
    a_cohort: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    result = apply_session_fees.execute(SESSION_2026)

    assert result.charged == ("app-0001", "app-0002")
    csc = a_cohort.get("app-0001")
    assert csc is not None
    assert csc.charge_for(ChargeKind.SESSION, SESSION_2026) is not None


def test_charges_each_program_and_level_its_own_amount(
    apply_session_fees: ApplySessionFees,
    a_cohort: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    apply_session_fees.execute(SESSION_2026)

    csc, mcb = a_cohort.get("app-0001"), a_cohort.get("app-0002")
    assert csc is not None and mcb is not None
    assert csc.outstanding == published_schedule.session_fee_for(CSC_PROGRAM_ID, Level(100))
    assert mcb.outstanding == published_schedule.session_fee_for(MCB_PROGRAM_ID, Level(100))


def test_an_account_the_schedule_does_not_price_is_skipped_and_named(
    apply_session_fees: ApplySessionFees,
    a_cohort: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    """Raising would stop a whole cohort being billed over one gap in a spreadsheet. The gap is
    reported instead, so somebody can go and fill it."""
    result = apply_session_fees.execute(SESSION_2026)

    assert result.unpriced == ("app-0003",)
    law = a_cohort.get("app-0003")
    assert law is not None
    assert law.charges == ()


def test_an_account_at_an_unpriced_level_is_skipped_too(
    apply_session_fees: ApplySessionFees,
    accounts: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    """The key is the pair: a priced program at an unpriced level is still unpriced."""
    accounts.add(Account.open("app-0009", CSC_PROGRAM_ID, level=Level(500)))
    result = apply_session_fees.execute(SESSION_2026)
    assert result.unpriced == ("app-0009",)


def test_a_redelivered_session_charges_nobody_twice(
    apply_session_fees: ApplySessionFees,
    a_cohort: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    first = apply_session_fees.execute(SESSION_2026)
    second = apply_session_fees.execute(SESSION_2026)

    assert first.charged == ("app-0001", "app-0002")
    assert second.charged == ()
    assert second.already_charged == ("app-0001", "app-0002")
    csc = a_cohort.get("app-0001")
    assert csc is not None
    assert len(csc.charges_for_session(SESSION_2026)) == 1


def test_a_rerun_after_a_partial_batch_finishes_the_job(
    apply_session_fees: ApplySessionFees,
    accounts: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    """A crash mid-batch under-charges rather than double-charging, and a rerun completes it —
    which is only true because raising a charge is idempotent."""
    accounts.add(Account.open("app-0001", CSC_PROGRAM_ID))
    apply_session_fees.execute(SESSION_2026)
    accounts.add(Account.open("app-0002", MCB_PROGRAM_ID))

    result = apply_session_fees.execute(SESSION_2026)

    assert result.charged == ("app-0002",)
    assert result.already_charged == ("app-0001",)


def test_a_session_with_no_schedule_at_all_stops_the_batch(
    apply_session_fees: ApplySessionFees, a_cohort: AccountRepositoryPort
) -> None:
    """Charging nobody would be indistinguishable from a session where nobody was priced."""
    with pytest.raises(FeeScheduleNotPublishedError):
        apply_session_fees.execute(SESSION_2026)

    csc = a_cohort.get("app-0001")
    assert csc is not None
    assert csc.charges == ()


def test_the_batch_reports_everything_it_considered(
    apply_session_fees: ApplySessionFees,
    a_cohort: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    result = apply_session_fees.execute(SESSION_2026)
    assert result.session_id == SESSION_2026
    assert result.considered == 3


def test_next_session_is_another_charge_on_the_same_ledger(
    apply_session_fees: ApplySessionFees,
    accounts: AccountRepositoryPort,
    schedules: InMemoryFeeScheduleRepository,
    published_schedule: FeeSchedule,
) -> None:
    """One continuous ledger from the acceptance fee onward: year two is an entry, not a new
    account."""
    accounts.add(Account.open("app-0001", CSC_PROGRAM_ID))
    schedules.add(
        FeeSchedule.for_session(
            "sess-2027",
            acceptance_fee=Money("20000"),
            matriculation_fee=Money("50000"),
            session_fees=(
                SessionFeeLine(program_id=CSC_PROGRAM_ID, level=Level(100), amount=Money("110000")),
            ),
        )
    )

    apply_session_fees.execute(SESSION_2026)
    apply_session_fees.execute("sess-2027")

    stored = accounts.get("app-0001")
    assert stored is not None
    assert len(stored.charges) == 2
    assert stored.outstanding == Money("210000")


def test_the_batch_announces_nothing(
    apply_session_fees: ApplySessionFees,
    a_cohort: AccountRepositoryPort,
    events: InMemoryEventPublisher,
    published_schedule: FeeSchedule,
) -> None:
    """A session fee gates registration, not matriculation, and raising one settles nothing."""
    apply_session_fees.execute(SESSION_2026)
    assert events.published == ()
