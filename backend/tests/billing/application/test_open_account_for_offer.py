"""``OpenAccountForOffer``, driven through its ports.

Three things are under test that the domain tests cannot see: that one accepted offer raises
*both* admission charges, that the amounts come from the published schedule rather than from
the caller, and that a redelivered event opens no second account.
"""

import pytest

from billing.adapters.outbound import InMemoryEventPublisher, InMemoryFeeScheduleRepository
from billing.application import (
    FeeScheduleNotPublishedError,
    OpenAccountForOffer,
    OpenAccountForOfferCommand,
)
from billing.domain import ChargeKind, FeeSchedule, Level, Money
from billing.ports import AccountRepositoryPort

APPLICANT_ID = "app-0001"
CSC_PROGRAM_ID = "prog-csc-bsc"
SESSION_2026 = "sess-2026"


def a_command(**overrides: object) -> OpenAccountForOfferCommand:
    fields: dict[str, object] = {
        "applicant_id": APPLICANT_ID,
        "program_id": CSC_PROGRAM_ID,
        "session_id": SESSION_2026,
    }
    fields.update(overrides)
    return OpenAccountForOfferCommand(**fields)  # type: ignore[arg-type]


def test_an_accepted_offer_opens_a_ledger_with_both_admission_charges(
    open_account_for_offer: OpenAccountForOffer,
    accounts: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    result = open_account_for_offer.execute(a_command())

    stored = accounts.get(APPLICANT_ID)
    assert stored is not None
    assert result.was_already_open is False
    assert result.acceptance_charge.amount == published_schedule.acceptance_fee
    assert result.matriculation_charge.amount == published_schedule.matriculation_fee
    assert [charge.kind for charge in stored.charges] == [
        ChargeKind.ACCEPTANCE,
        ChargeKind.MATRICULATION,
    ]


def test_only_the_acceptance_charge_gates_matriculation(
    open_account_for_offer: OpenAccountForOffer, published_schedule: FeeSchedule
) -> None:
    """CLAUDE.md section 4: the matriculation fee is an outstanding balance and nothing more."""
    result = open_account_for_offer.execute(a_command())
    assert result.acceptance_charge.gates_matriculation
    assert not result.matriculation_charge.gates_matriculation


def test_the_account_is_opened_for_the_offered_program_at_the_entry_level(
    open_account_for_offer: OpenAccountForOffer,
    accounts: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    """The offered program, which is not always the one applied for."""
    open_account_for_offer.execute(a_command(program_id="prog-mcb-bsc"))
    stored = accounts.get(APPLICANT_ID)
    assert stored is not None
    assert stored.program_id == "prog-mcb-bsc"
    assert stored.level == Level(100)


def test_a_level_may_be_stated_when_the_caller_knows_one(
    open_account_for_offer: OpenAccountForOffer,
    accounts: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    open_account_for_offer.execute(a_command(level=200))
    stored = accounts.get(APPLICANT_ID)
    assert stored is not None
    assert stored.level == Level(200)


def test_the_amounts_come_from_the_schedule_and_not_from_the_caller(
    open_account_for_offer: OpenAccountForOffer,
    schedules: InMemoryFeeScheduleRepository,
) -> None:
    """A caller that could state the acceptance fee could state it wrongly, and the applicant
    would be gated on a figure nobody set."""
    schedules.add(
        FeeSchedule.for_session(
            "sess-2027",
            acceptance_fee=Money("25000"),
            matriculation_fee=Money("55000"),
        )
    )

    result = open_account_for_offer.execute(a_command(session_id="sess-2027"))

    assert result.acceptance_charge.amount == Money("25000")
    assert result.matriculation_charge.amount == Money("55000")


def test_a_redelivered_offer_opens_no_second_account_and_charges_nothing_twice(
    open_account_for_offer: OpenAccountForOffer,
    accounts: AccountRepositoryPort,
    published_schedule: FeeSchedule,
) -> None:
    """An at-least-once bus replays; a second acceptance fee is the failure that would cause."""
    first = open_account_for_offer.execute(a_command())
    second = open_account_for_offer.execute(a_command())

    stored = accounts.get(APPLICANT_ID)
    assert stored is not None
    assert first.was_already_open is False
    assert second.was_already_open is True
    assert len(stored.charges) == 2
    assert stored.total_charged == (
        published_schedule.acceptance_fee + published_schedule.matriculation_fee
    )


def test_an_unpriced_session_is_refused(
    open_account_for_offer: OpenAccountForOffer, accounts: AccountRepositoryPort
) -> None:
    """An account with no acceptance charge would leave matriculation gated on nothing."""
    with pytest.raises(FeeScheduleNotPublishedError):
        open_account_for_offer.execute(a_command())
    assert accounts.get(APPLICANT_ID) is None


def test_opening_an_account_announces_nothing(
    open_account_for_offer: OpenAccountForOffer,
    events: InMemoryEventPublisher,
    published_schedule: FeeSchedule,
) -> None:
    """Charges are raised, not settled: a bill nobody has paid is not an ``AcceptanceFeePaid``."""
    open_account_for_offer.execute(a_command())
    assert events.published == ()
