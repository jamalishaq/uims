"""``RecordPayment``: the only way money gets onto a ledger.

Two of Phase 5.1's three claims are made here rather than in the domain tests, because they
are claims about what the *system* does and not only what the aggregate does: a duplicate
gateway reference must not reach the repository, and ``AcceptanceFeePaid`` must be announced
exactly once per applicant.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from billing.adapters.outbound import InMemoryEventPublisher
from billing.application import (
    AccountNotFoundError,
    RecordPayment,
    RecordPaymentCommand,
)
from billing.domain import (
    AcceptanceFeePaid,
    Account,
    ChargeKind,
    DuplicatePaymentIgnored,
    InvalidAmountError,
    Money,
    PaymentApplied,
)
from billing.ports import AccountRepositoryPort

APPLICANT_ID = "app-0001"
MATRIC_NUMBER = "260591001"
PROGRAM_ID = "prog-csc-bsc"
SESSION_2026 = "sess-2026"

AUGUST = datetime(2026, 8, 1, 9, 30)
SEPTEMBER = datetime(2026, 9, 1, 9, 30)


def a_command(**overrides: object) -> RecordPaymentCommand:
    fields: dict[str, object] = {
        "party_id": APPLICANT_ID,
        "gateway_ref": "pay-abc-123",
        "amount": Decimal("20000"),
        "received_at": AUGUST,
    }
    fields.update(overrides)
    return RecordPaymentCommand(**fields)  # type: ignore[arg-type]


@pytest.fixture
def an_admitted_account(accounts: AccountRepositoryPort) -> Account:
    """What ``OfferAccepted`` leaves behind: 20,000 gating and 50,000 not."""
    account = Account.open(APPLICANT_ID, PROGRAM_ID)
    account.raise_acceptance_fee(SESSION_2026, Money("20000"))
    account.raise_matriculation_fee(SESSION_2026, Money("50000"))
    accounts.add(account)
    return account


def test_a_payment_lands_on_the_ledger_and_is_allocated(
    record_payment: RecordPayment, an_admitted_account: Account
) -> None:
    result = record_payment.execute(a_command(amount=Decimal("5000")))

    assert result.was_duplicate is False
    assert isinstance(result.outcome, PaymentApplied)
    assert an_admitted_account.total_paid == Money("5000")
    assert an_admitted_account.charge_for(ChargeKind.ACCEPTANCE, SESSION_2026).allocated == Money(  # type: ignore[union-attr]
        "5000"
    )


def test_the_same_gateway_ref_recorded_twice_changes_the_ledger_once(
    record_payment: RecordPayment, an_admitted_account: Account
) -> None:
    """Phase 5.1's first claim, at the seam a retrying webhook actually hits."""
    first = record_payment.execute(a_command())
    second = record_payment.execute(a_command(received_at=SEPTEMBER))

    assert first.was_duplicate is False
    assert second.was_duplicate is True
    assert isinstance(second.outcome, DuplicatePaymentIgnored)
    assert len(an_admitted_account.payments) == 1
    assert an_admitted_account.total_paid == Money("20000")
    assert an_admitted_account.outstanding == Money("50000")


def test_an_overpayment_leaves_a_credit_balance(
    record_payment: RecordPayment, an_admitted_account: Account
) -> None:
    """Phase 5.1's second claim. Never assume balance ≤ charges."""
    record_payment.execute(a_command(amount=Decimal("100000")))

    assert an_admitted_account.outstanding == Money.zero()
    assert an_admitted_account.credit_balance == Money("30000")


def test_the_acceptance_fee_paid_event_fires_exactly_once_per_applicant(
    record_payment: RecordPayment,
    an_admitted_account: Account,
    events: InMemoryEventPublisher,
) -> None:
    """Phase 5.1's third claim: through part payments, the settling payment, its replay, and
    every payment after it, the fact is announced once."""
    for index, amount in enumerate(["5000", "5000", "10000", "50000"]):
        record_payment.execute(a_command(gateway_ref=f"ref-{index}", amount=Decimal(amount)))
    record_payment.execute(a_command(gateway_ref="ref-2", amount=Decimal("10000")))

    assert events.published == (AcceptanceFeePaid(applicant_id=APPLICANT_ID),)


def test_nothing_is_announced_before_the_acceptance_fee_is_settled(
    record_payment: RecordPayment,
    an_admitted_account: Account,
    events: InMemoryEventPublisher,
) -> None:
    record_payment.execute(a_command(amount=Decimal("19999.99")))
    assert events.published == ()


def test_a_duplicate_announces_nothing(
    record_payment: RecordPayment,
    an_admitted_account: Account,
    events: InMemoryEventPublisher,
) -> None:
    """Otherwise every webhook retry would re-announce a fact Admissions has already acted on."""
    record_payment.execute(a_command())
    events.clear()

    result = record_payment.execute(a_command())

    assert result.published == ()
    assert events.published == ()


def test_the_event_names_the_applicant_admissions_is_waiting_on(
    record_payment: RecordPayment,
    an_admitted_account: Account,
    events: InMemoryEventPublisher,
) -> None:
    """CLAUDE.md section 3: Admissions consumes ``AcceptanceFeePaid(applicant_id)``."""
    record_payment.execute(a_command())
    assert events.published[0].applicant_id == APPLICANT_ID


def test_a_payment_quoting_the_matric_number_reaches_the_same_ledger(
    record_payment: RecordPayment,
    an_admitted_account: Account,
    accounts: AccountRepositoryPort,
) -> None:
    """One continuous ledger: the payer's id changed, the account did not."""
    an_admitted_account.link_student_id(MATRIC_NUMBER)
    accounts.save(an_admitted_account)

    result = record_payment.execute(a_command(party_id=MATRIC_NUMBER))

    assert result.party_id == APPLICANT_ID
    assert an_admitted_account.total_paid == Money("20000")


def test_money_for_a_party_with_no_ledger_is_refused(record_payment: RecordPayment) -> None:
    """Opening an account here would invent a party out of a gateway reference."""
    with pytest.raises(AccountNotFoundError):
        record_payment.execute(a_command(party_id="app-9999"))


def test_a_float_amount_is_refused(
    record_payment: RecordPayment, an_admitted_account: Account
) -> None:
    """An adapter that read a gateway's JSON number carelessly fails here, not three decimal
    places later."""
    with pytest.raises(InvalidAmountError):
        record_payment.execute(a_command(amount=20000.5))


def test_the_ledger_records_the_amount_that_arrived(
    record_payment: RecordPayment, an_admitted_account: Account
) -> None:
    """CLAUDE.md section 3: never the intent's amount. A part payment against a 20,000 charge
    is 12,500 on the ledger and a charge still outstanding."""
    record_payment.execute(a_command(amount=Decimal("12500.50")))

    assert an_admitted_account.total_paid == Money("12500.50")
    assert not an_admitted_account.acceptance_fee_settled
