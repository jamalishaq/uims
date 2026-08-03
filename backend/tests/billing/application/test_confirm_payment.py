"""``ConfirmPayment``: two aggregates, one request, and the order they are written in.

The claim these tests exist to hold is the one in the use case's docstring — the ledger is
written *before* the intent, so that a crash between them leaves a state the reconciliation
sweep can heal rather than one nothing will ever look at again.

Proving an ordering needs a seam that can fail in the middle, which is what
:class:`SaveRefusingIntents` provides: a hand-written fake in the manner of the rest of this
suite, no mock library involved.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from billing.adapters.outbound import InMemoryEventPublisher
from billing.application import (
    ConfirmPayment,
    ConfirmPaymentCommand,
    PaymentIntentNotFoundError,
    RecordPayment,
)
from billing.domain import (
    AcceptanceFeePaid,
    Account,
    DuplicatePaymentIgnored,
    InvalidPaymentIntentError,
    Money,
    PaymentApplied,
    PaymentIntent,
    PaymentIntentAlreadyResolved,
    PaymentIntentFinalError,
    PaymentIntentStatus,
)
from billing.ports import AccountRepositoryPort, PaymentIntentRepositoryPort

APPLICANT_ID = "app-0001"
MATRIC_NUMBER = "260591001"
PROGRAM_ID = "prog-csc-bsc"
SESSION_2026 = "sess-2026"
REFERENCE = "psk-ref-0001"

JULY = datetime(2026, 7, 1, 9, 30)
AUGUST = datetime(2026, 8, 1, 9, 30)


def a_command(**overrides: object) -> ConfirmPaymentCommand:
    fields: dict[str, object] = {
        "reference": REFERENCE,
        "paid_at": AUGUST,
        "succeeded": True,
        "amount": Decimal("20000"),
    }
    fields.update(overrides)
    return ConfirmPaymentCommand(**fields)  # type: ignore[arg-type]


@pytest.fixture
async def an_admitted_account(accounts: AccountRepositoryPort) -> Account:
    account = Account.open(APPLICANT_ID, PROGRAM_ID)
    account.raise_acceptance_fee(SESSION_2026, Money("20000"))
    account.raise_matriculation_fee(SESSION_2026, Money("50000"))
    await accounts.add(account)
    return account


@pytest.fixture
async def an_open_intent(
    an_admitted_account: Account, intents: PaymentIntentRepositoryPort
) -> PaymentIntent:
    intent = PaymentIntent.initiate(
        reference=REFERENCE, party_id=APPLICANT_ID, amount=Money("20000"), initiated_at=JULY
    )
    await intents.add(intent)
    return intent


class TestBankingTheMoney:
    async def test_a_confirmation_puts_the_money_on_the_ledger_and_moves_the_intent(
        self,
        confirm_payment: ConfirmPayment,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
    ) -> None:
        result = await confirm_payment.execute(a_command())

        assert isinstance(result.ledger_outcome, PaymentApplied)
        assert result.was_replay is False
        assert result.amount_matched is True
        assert result.party_id == APPLICANT_ID
        assert an_admitted_account.total_paid == Money("20000")
        assert an_open_intent.status is PaymentIntentStatus.CONFIRMED

    async def test_the_ledger_records_the_confirmed_amount_and_not_the_intents(
        self,
        confirm_payment: ConfirmPayment,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
    ) -> None:
        await confirm_payment.execute(a_command(amount=Decimal("12000")))

        assert an_admitted_account.total_paid == Money("12000")
        assert an_open_intent.amount == Money("20000")
        assert an_open_intent.confirmed_amount == Money("12000")
        assert an_admitted_account.outstanding == Money("58000")

    async def test_settling_the_gating_charge_is_announced(
        self,
        confirm_payment: ConfirmPayment,
        an_open_intent: PaymentIntent,
        events: InMemoryEventPublisher,
    ) -> None:
        """The webhook path still produces ``AcceptanceFeePaid`` — via ``RecordPayment``."""
        await confirm_payment.execute(a_command())

        assert events.published == (AcceptanceFeePaid(applicant_id=APPLICANT_ID),)

    async def test_a_replay_reaches_the_ledgers_existing_no_op(
        self,
        confirm_payment: ConfirmPayment,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
    ) -> None:
        await confirm_payment.execute(a_command())

        replay = await confirm_payment.execute(a_command())

        assert replay.was_replay is True
        assert isinstance(replay.ledger_outcome, DuplicatePaymentIgnored)
        assert isinstance(replay.intent_outcome, PaymentIntentAlreadyResolved)
        assert len(an_admitted_account.payments) == 1

    async def test_the_party_is_taken_from_the_intent(
        self,
        confirm_payment: ConfirmPayment,
        intents: PaymentIntentRepositoryPort,
        accounts: AccountRepositoryPort,
    ) -> None:
        """An intent opened against a matric number credits the one continuous ledger."""
        account = Account.open(APPLICANT_ID, PROGRAM_ID)
        account.raise_acceptance_fee(SESSION_2026, Money("20000"))
        account.link_student_id(MATRIC_NUMBER)
        await accounts.add(account)
        await intents.add(
            PaymentIntent.initiate(
                reference=REFERENCE,
                party_id=MATRIC_NUMBER,
                amount=Money("20000"),
                initiated_at=JULY,
            )
        )

        result = await confirm_payment.execute(a_command())

        assert result.party_id == MATRIC_NUMBER
        assert account.total_paid == Money("20000")


class TestOrdering:
    """The ledger is written first. See ``confirm_payment``'s module docstring for why."""

    class SaveRefusingIntents(PaymentIntentRepositoryPort):
        """Wraps a real repository and fails every ``save``, as a dying process would."""

        def __init__(self, inner: PaymentIntentRepositoryPort) -> None:
            self._inner = inner

        async def add(self, intent: PaymentIntent) -> None:
            await self._inner.add(intent)

        async def save(self, intent: PaymentIntent) -> None:
            raise RuntimeError("the process died before the intent could be written")

        async def get(self, reference: str) -> PaymentIntent | None:
            return await self._inner.get(reference)

        async def all_initiated(self) -> tuple[PaymentIntent, ...]:
            return await self._inner.all_initiated()

    async def test_the_money_is_on_the_ledger_even_when_the_intent_cannot_be_saved(
        self,
        intents: PaymentIntentRepositoryPort,
        record_payment: RecordPayment,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
    ) -> None:
        """A crash after the ledger write leaves money recorded and an intent to heal.

        The reverse order would leave an intent claiming to be confirmed over an account that
        never received the money — and nothing would come back to check, because the sweep
        only looks at intents that are still open.
        """
        confirm = ConfirmPayment(self.SaveRefusingIntents(intents), record_payment)

        with pytest.raises(RuntimeError):
            await confirm.execute(a_command())

        assert an_admitted_account.total_paid == Money("20000"), "the ledger was written first"


class TestRefusals:
    async def test_a_reference_with_no_intent_is_refused_and_writes_nothing(
        self, confirm_payment: ConfirmPayment, an_admitted_account: Account
    ) -> None:
        with pytest.raises(PaymentIntentNotFoundError):
            await confirm_payment.execute(a_command(reference="psk-ref-nobody-opened"))

        assert an_admitted_account.payments == ()

    def test_a_success_without_an_amount_cannot_be_commanded(self) -> None:
        """Refused at construction, so no half-applied confirmation is possible."""
        with pytest.raises(InvalidPaymentIntentError, match="without an amount"):
            ConfirmPaymentCommand(reference=REFERENCE, paid_at=AUGUST, succeeded=True)

    async def test_a_reported_failure_leaves_the_ledger_alone(
        self,
        confirm_payment: ConfirmPayment,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
        events: InMemoryEventPublisher,
    ) -> None:
        result = await confirm_payment.execute(
            a_command(succeeded=False, amount=None, failure_reason="insufficient funds")
        )

        assert result.ledger_outcome is None
        assert an_admitted_account.payments == ()
        assert events.published == ()
        assert an_open_intent.status is PaymentIntentStatus.FAILED
        assert an_open_intent.failure_reason == "insufficient funds"

    async def test_a_gateway_that_confirms_then_fails_is_refused(
        self, confirm_payment: ConfirmPayment, an_open_intent: PaymentIntent
    ) -> None:
        await confirm_payment.execute(a_command())

        with pytest.raises(PaymentIntentFinalError):
            await confirm_payment.execute(a_command(succeeded=False, amount=None))

    async def test_a_gateway_that_fails_then_confirms_banks_the_money_and_then_raises(
        self,
        confirm_payment: ConfirmPayment,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
    ) -> None:
        """The deliberate consequence of writing the ledger first.

        Money that moved is recorded whatever the intent says; it is the *contradiction* that
        needs a person, not the payment. Losing the money to keep the intent tidy would be the
        wrong trade — an untidy intent is a question somebody answers, and unrecorded money is
        a student who cannot register against a debt they have settled.
        """
        await confirm_payment.execute(a_command(succeeded=False, amount=None))

        with pytest.raises(PaymentIntentFinalError):
            await confirm_payment.execute(a_command())

        assert an_admitted_account.total_paid == Money("20000")
