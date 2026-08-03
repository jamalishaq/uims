"""``SessionOpened`` from Faculty & Department to Billing, over the real bus.

The build playbook's Phase 5.1 line: "SessionOpened handler batch-applies FeeSchedule". This
module exercises both contexts at once, and it is a test rather than production code for the
reason the dependency rule gives — neither context may import the other, so the introduction
has to be made by somebody outside both. The composition root doing it is
``tests/billing/conftest.py``; here it is used.

Nothing is stubbed between the two ends. A registrar opens a real ``Session`` aggregate over
in Faculty & Department, which publishes through :class:`InMemoryEventBus`; the bus serialises
the event with ``dataclasses.asdict`` and hands the payload to Billing's real handler, use
case, aggregates and repository. The only thing that is not real is the transport, and Phase 6
replaces that alone.

Worth noticing in passing: ``SessionOpened`` carries an ``AcademicYear``, which arrives here as
a nested mapping. Billing reads past it. That is what "consumers never import these classes"
looks like from the consuming side.
"""

import pytest

from billing.adapters.outbound import InMemoryFeeScheduleRepository
from billing.domain import Account, ChargeKind, FeeSchedule, Money
from billing.ports import AccountRepositoryPort
from faculty_department.adapters.outbound import InMemoryEventBus
from faculty_department.domain import (
    AcademicYear,
    Semester,
    SemesterOrdinal,
    Session,
    SessionAlreadyOpenError,
)

SESSION_ID = "sess-2026"
CSC_PROGRAM_ID = "prog-csc-bsc"
LAW_PROGRAM_ID = "prog-law-llb"


def a_session(session_id: str = SESSION_ID, year: int = 2026) -> Session:
    """The calendar as Faculty & Department holds it: a year and its two semesters."""
    return Session.plan(
        session_id,
        AcademicYear(year),
        (
            Semester(f"{session_id}-1", SemesterOrdinal.FIRST),
            Semester(f"{session_id}-2", SemesterOrdinal.SECOND),
        ),
    )


@pytest.fixture
def a_cohort(accounts: AccountRepositoryPort) -> AccountRepositoryPort:
    accounts.add(Account.open("app-0001", CSC_PROGRAM_ID))
    accounts.add(Account.open("app-0002", LAW_PROGRAM_ID))
    return accounts


def test_opening_a_session_charges_every_priced_account(
    wired_bus: InMemoryEventBus,
    a_cohort: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    wired_bus.publish(a_session().open())

    charged = a_cohort.get("app-0001")
    assert charged is not None
    session_fee = charged.charge_for(ChargeKind.SESSION, SESSION_ID)
    assert session_fee is not None
    assert session_fee.amount == Money("100000")


def test_an_account_the_schedule_does_not_price_is_left_alone(
    wired_bus: InMemoryEventBus,
    a_cohort: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    wired_bus.publish(a_session().open())

    skipped = a_cohort.get("app-0002")
    assert skipped is not None
    assert skipped.charges == ()


def test_a_replayed_session_charges_nobody_twice(
    wired_bus: InMemoryEventBus,
    a_cohort: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    """At-least-once delivery is normal; a second session fee is the failure that would cause."""
    event = a_session().open()
    wired_bus.publish(event)
    wired_bus.publish(event)

    charged = a_cohort.get("app-0001")
    assert charged is not None
    assert len(charged.charges_for_session(SESSION_ID)) == 1
    assert charged.outstanding == Money("100000")


def test_a_session_that_cannot_open_charges_nobody(
    wired_bus: InMemoryEventBus,
    a_cohort: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    """The domain over there refuses before anything is published, so nothing reaches here —
    the same shape as Academic Records' "a submission the domain rejected must not arrive"."""
    session = a_session()
    session.open()

    with pytest.raises(SessionAlreadyOpenError):
        session.open()

    assert wired_bus.published == ()
    charged = a_cohort.get("app-0001")
    assert charged is not None
    assert charged.charges == ()


def test_billing_subscribes_to_the_session_and_to_nothing_else(
    wired_bus: InMemoryEventBus,
) -> None:
    """``GradeSubmitted`` is Academic Records' business, and a bus Billing over-subscribed to
    would be this context reacting to facts it has no interest in."""
    assert len(wired_bus.subscribers_for("SessionOpened")) == 1
    assert wired_bus.subscribers_for("GradeSubmitted") == ()


def test_next_year_is_another_charge_on_the_same_ledger(
    wired_bus: InMemoryEventBus,
    a_cohort: AccountRepositoryPort,
    published_schedule: FeeSchedule,
    schedules: InMemoryFeeScheduleRepository,
) -> None:
    """One continuous ledger: a second session opening adds an entry, not an account."""
    schedules.add(
        FeeSchedule.for_session(
            "sess-2027",
            acceptance_fee=Money("20000"),
            matriculation_fee=Money("50000"),
            session_fees=published_schedule.session_fee_lines,
        )
    )

    wired_bus.publish(a_session().open())
    wired_bus.publish(a_session("sess-2027", 2027).open())

    charged = a_cohort.get("app-0001")
    assert charged is not None
    assert len(charged.charges) == 2
    assert charged.outstanding == Money("200000")
