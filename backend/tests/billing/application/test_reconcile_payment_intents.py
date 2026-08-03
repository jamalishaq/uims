"""``ReconcilePaymentIntents``: the sweep that catches the payment nobody told us about.

The headline test is
:meth:`TestTheLostWebhook.test_a_payment_whose_webhook_never_arrived_is_recovered` — the
scenario CLAUDE.md section 3 names as the reason any of this exists. The rest is mostly about
what the sweep declines to do: it never asks about an intent still inside its TTL, never
concludes anything from a clock, and never writes an intent off because the gateway was
unreachable.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from billing.adapters.outbound import InMemoryEventPublisher, StubPaymentGateway
from billing.application import ReconcilePaymentIntents
from billing.domain import (
    AcceptanceFeePaid,
    Account,
    GatewayStatus,
    GatewayVerification,
    Money,
    PaymentIntent,
    PaymentIntentStatus,
)
from billing.ports import AccountRepositoryPort, PaymentIntentRepositoryPort

APPLICANT_ID = "app-0001"
PROGRAM_ID = "prog-csc-bsc"
SESSION_2026 = "sess-2026"
REFERENCE = "psk-ref-0001"

NINE_THIRTY = datetime(2026, 7, 1, 9, 30)
AN_HOUR_LATER = NINE_THIRTY + timedelta(hours=1)
NEXT_DAY = NINE_THIRTY + timedelta(days=1)


@pytest.fixture
def an_admitted_account(accounts: AccountRepositoryPort) -> Account:
    account = Account.open(APPLICANT_ID, PROGRAM_ID)
    account.raise_acceptance_fee(SESSION_2026, Money("20000"))
    account.raise_matriculation_fee(SESSION_2026, Money("50000"))
    accounts.add(account)
    return account


@pytest.fixture
def an_open_intent(
    an_admitted_account: Account, intents: PaymentIntentRepositoryPort
) -> PaymentIntent:
    intent = PaymentIntent.initiate(
        reference=REFERENCE, party_id=APPLICANT_ID, amount=Money("20000"), initiated_at=NINE_THIRTY
    )
    intents.add(intent)
    return intent


class TestWhatIsWorthAsking:
    def test_an_intent_inside_its_ttl_is_never_even_asked_about(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        gateway: StubPaymentGateway,
    ) -> None:
        """The absence of the call is the assertion. A sweep that chased every open checkout
        would hammer the gateway with questions about people still typing their card details.
        """
        swept = reconcile_payment_intents.execute(NINE_THIRTY + timedelta(minutes=30))

        assert gateway.asked == ()
        assert swept.examined == 0
        assert swept.skipped == 1
        assert an_open_intent.status is PaymentIntentStatus.INITIATED

    def test_an_answered_intent_is_never_swept_again(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        intents: PaymentIntentRepositoryPort,
        gateway: StubPaymentGateway,
    ) -> None:
        an_open_intent.fail("insufficient funds", at=AN_HOUR_LATER)
        intents.save(an_open_intent)

        swept = reconcile_payment_intents.execute(NEXT_DAY)

        assert gateway.asked == ()
        assert swept.examined == 0
        assert swept.skipped == 0


class TestTheLostWebhook:
    def test_a_payment_whose_webhook_never_arrived_is_recovered(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
        gateway: StubPaymentGateway,
        events: InMemoryEventPublisher,
    ) -> None:
        """The whole point. Money was taken, the callback was dropped, the sweep finds it."""
        gateway.will_answer(
            GatewayVerification(
                reference=REFERENCE,
                status=GatewayStatus.SUCCESS,
                amount=Money("20000"),
                paid_at=AN_HOUR_LATER,
            )
        )

        swept = reconcile_payment_intents.execute(NEXT_DAY)

        assert swept.confirmed == (REFERENCE,)
        assert swept.recovered_money is True
        assert an_admitted_account.total_paid == Money("20000")
        assert an_open_intent.status is PaymentIntentStatus.CONFIRMED
        assert events.published == (AcceptanceFeePaid(applicant_id=APPLICANT_ID),), (
            "the recovered payment settles the gating charge exactly as a webhook's would"
        )

    def test_the_recovered_amount_is_the_gateways_and_not_the_intents(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
        gateway: StubPaymentGateway,
    ) -> None:
        gateway.will_answer(
            GatewayVerification(
                reference=REFERENCE, status=GatewayStatus.SUCCESS, amount=Money(Decimal("15000"))
            )
        )

        reconcile_payment_intents.execute(NEXT_DAY)

        assert an_admitted_account.total_paid == Money("15000")
        assert an_open_intent.confirmed_amount == Money("15000")
        assert an_open_intent.amount == Money("20000")

    def test_a_verification_with_no_instant_is_dated_by_discovery(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
        gateway: StubPaymentGateway,
    ) -> None:
        gateway.will_answer(
            GatewayVerification(
                reference=REFERENCE, status=GatewayStatus.SUCCESS, amount=Money("20000")
            )
        )

        reconcile_payment_intents.execute(NEXT_DAY)

        assert an_admitted_account.payments[0].received_at == NEXT_DAY


class TestTheOtherAnswers:
    def test_a_stated_failure_moves_the_intent_and_not_the_ledger(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
        gateway: StubPaymentGateway,
    ) -> None:
        gateway.will_answer(GatewayVerification(reference=REFERENCE, status=GatewayStatus.FAILED))

        swept = reconcile_payment_intents.execute(NEXT_DAY)

        assert swept.failed == (REFERENCE,)
        assert an_open_intent.status is PaymentIntentStatus.FAILED
        assert an_admitted_account.payments == ()

    def test_a_reference_the_gateway_has_never_heard_of_is_abandoned(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
    ) -> None:
        """The checkout somebody opened and walked away from. Most of them, in practice."""
        swept = reconcile_payment_intents.execute(NEXT_DAY)

        assert swept.abandoned == (REFERENCE,)
        assert an_open_intent.status is PaymentIntentStatus.ABANDONED
        assert an_admitted_account.payments == ()

    def test_a_payment_still_in_flight_is_left_completely_alone(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        gateway: StubPaymentGateway,
    ) -> None:
        """Abandoning a payment the gateway is processing is the mistake this all avoids."""
        gateway.will_answer(GatewayVerification(reference=REFERENCE, status=GatewayStatus.PENDING))

        swept = reconcile_payment_intents.execute(NEXT_DAY)

        assert swept.pending == (REFERENCE,)
        assert swept.abandoned == ()
        assert an_open_intent.status is PaymentIntentStatus.INITIATED, "still open, on purpose"


class TestAnUnreachableGateway:
    def test_an_unanswered_question_leaves_the_intent_open(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        gateway: StubPaymentGateway,
    ) -> None:
        """A network failure is evidence about the network, not about somebody's card."""
        gateway.will_be_unreachable_for(REFERENCE)

        swept = reconcile_payment_intents.execute(NEXT_DAY)

        assert swept.unreachable == (REFERENCE,)
        assert swept.abandoned == ()
        assert an_open_intent.status is PaymentIntentStatus.INITIATED

    def test_one_unreachable_reference_does_not_take_the_batch_down(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        accounts: AccountRepositoryPort,
        intents: PaymentIntentRepositoryPort,
        gateway: StubPaymentGateway,
    ) -> None:
        second = Account.open("app-0002", PROGRAM_ID)
        second.raise_acceptance_fee(SESSION_2026, Money("20000"))
        accounts.add(second)
        intents.add(
            PaymentIntent.initiate(
                reference="psk-ref-0002",
                party_id="app-0002",
                amount=Money("20000"),
                initiated_at=NINE_THIRTY,
            )
        )
        gateway.will_be_unreachable_for(REFERENCE)
        gateway.will_answer(
            GatewayVerification(
                reference="psk-ref-0002", status=GatewayStatus.SUCCESS, amount=Money("20000")
            )
        )

        swept = reconcile_payment_intents.execute(NEXT_DAY)

        assert swept.examined == 2
        assert swept.unreachable == (REFERENCE,)
        assert swept.confirmed == ("psk-ref-0002",)
        assert second.total_paid == Money("20000")

    def test_the_next_sweep_asks_again(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
        gateway: StubPaymentGateway,
    ) -> None:
        gateway.will_be_unreachable_for(REFERENCE)
        reconcile_payment_intents.execute(NEXT_DAY)

        gateway.will_answer(
            GatewayVerification(
                reference=REFERENCE, status=GatewayStatus.SUCCESS, amount=Money("20000")
            )
        )
        swept = reconcile_payment_intents.execute(NEXT_DAY + timedelta(hours=1))

        assert swept.confirmed == (REFERENCE,)
        assert an_admitted_account.total_paid == Money("20000")


class TestRunningItTwice:
    def test_a_sweep_is_safe_to_repeat(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
        gateway: StubPaymentGateway,
        events: InMemoryEventPublisher,
    ) -> None:
        gateway.will_answer(
            GatewayVerification(
                reference=REFERENCE, status=GatewayStatus.SUCCESS, amount=Money("20000")
            )
        )

        first = reconcile_payment_intents.execute(NEXT_DAY)
        second = reconcile_payment_intents.execute(NEXT_DAY + timedelta(hours=1))

        assert first.confirmed == (REFERENCE,)
        assert second.examined == 0, "the intent is answered and no longer open"
        assert len(an_admitted_account.payments) == 1
        assert events.published == (AcceptanceFeePaid(applicant_id=APPLICANT_ID),)

    def test_an_abandoned_intent_is_not_swept_a_second_time(
        self,
        reconcile_payment_intents: ReconcilePaymentIntents,
        an_open_intent: PaymentIntent,
        gateway: StubPaymentGateway,
    ) -> None:
        reconcile_payment_intents.execute(NEXT_DAY)

        swept = reconcile_payment_intents.execute(NEXT_DAY + timedelta(hours=1))

        assert swept.examined == 0
        assert gateway.asked == (REFERENCE,), "asked once, not twice"
