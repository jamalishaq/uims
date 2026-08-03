"""``InitiatePayment``: writing down that money was asked for, and moving none of it."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from billing.application import (
    AccountNotFoundError,
    InitiatePayment,
    InitiatePaymentCommand,
)
from billing.domain import (
    DEFAULT_INTENT_TTL,
    Account,
    InvalidAmountError,
    Money,
    PaymentIntentStatus,
)
from billing.ports import (
    AccountRepositoryPort,
    DuplicateAggregateError,
    PaymentIntentRepositoryPort,
)

APPLICANT_ID = "app-0001"
MATRIC_NUMBER = "260591001"
PROGRAM_ID = "prog-csc-bsc"
SESSION_2026 = "sess-2026"
REFERENCE = "psk-ref-0001"

JULY = datetime(2026, 7, 1, 9, 30)


def a_command(**overrides: object) -> InitiatePaymentCommand:
    fields: dict[str, object] = {
        "party_id": APPLICANT_ID,
        "reference": REFERENCE,
        "amount": Decimal("20000"),
        "initiated_at": JULY,
    }
    fields.update(overrides)
    return InitiatePaymentCommand(**fields)  # type: ignore[arg-type]


@pytest.fixture
def an_admitted_account(accounts: AccountRepositoryPort) -> Account:
    account = Account.open(APPLICANT_ID, PROGRAM_ID)
    account.raise_acceptance_fee(SESSION_2026, Money("20000"))
    accounts.add(account)
    return account


def test_a_checkout_is_recorded_as_initiated(
    initiate_payment: InitiatePayment,
    an_admitted_account: Account,
    intents: PaymentIntentRepositoryPort,
) -> None:
    result = initiate_payment.execute(a_command())

    assert result.party_id == APPLICANT_ID
    assert result.intent.status is PaymentIntentStatus.INITIATED
    assert result.intent.amount == Money("20000")
    assert intents.get(REFERENCE) is not None


def test_opening_a_checkout_moves_no_money(
    initiate_payment: InitiatePayment, an_admitted_account: Account
) -> None:
    """Most checkouts are never completed. None of them may touch a ledger."""
    initiate_payment.execute(a_command())

    assert an_admitted_account.payments == ()
    assert an_admitted_account.total_paid == Money.zero()
    assert an_admitted_account.outstanding == Money("20000")


def test_the_ttl_defaults_to_billings_own(
    initiate_payment: InitiatePayment, an_admitted_account: Account
) -> None:
    assert initiate_payment.execute(a_command()).intent.ttl == DEFAULT_INTENT_TTL


def test_a_ttl_may_be_given_at_the_call_site(
    initiate_payment: InitiatePayment, an_admitted_account: Account
) -> None:
    result = initiate_payment.execute(a_command(ttl=timedelta(minutes=20)))

    assert result.intent.expires_at == JULY + timedelta(minutes=20)


def test_money_asked_of_a_party_with_no_ledger_is_refused(
    initiate_payment: InitiatePayment, intents: PaymentIntentRepositoryPort
) -> None:
    with pytest.raises(AccountNotFoundError):
        initiate_payment.execute(a_command(party_id="app-nobody"))

    assert intents.get(REFERENCE) is None


def test_a_reference_can_only_be_claimed_once(
    initiate_payment: InitiatePayment, an_admitted_account: Account
) -> None:
    """A gateway reference identifies one movement of money, on both aggregates."""
    initiate_payment.execute(a_command())

    with pytest.raises(DuplicateAggregateError):
        initiate_payment.execute(a_command(amount=Decimal("999")))


def test_an_intent_opened_against_a_matric_number_is_keyed_to_the_one_ledger(
    initiate_payment: InitiatePayment, accounts: AccountRepositoryPort
) -> None:
    """The party-id abstraction: the intent stores whichever id the account is filed under."""
    account = Account.open(APPLICANT_ID, PROGRAM_ID)
    account.link_student_id(MATRIC_NUMBER)
    accounts.add(account)

    result = initiate_payment.execute(a_command(party_id=MATRIC_NUMBER))

    assert result.party_id == APPLICANT_ID
    assert result.intent.party_id == APPLICANT_ID


def test_a_float_amount_is_refused(
    initiate_payment: InitiatePayment, an_admitted_account: Account
) -> None:
    with pytest.raises(InvalidAmountError):
        initiate_payment.execute(a_command(amount=20000.0))
