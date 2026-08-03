"""The ``PaymentIntent`` state machine, its TTL, and what it refuses.

Zero infrastructure, per CLAUDE.md section 2: an intent is built directly and every instant is
a constant, because there is no clock in this system and a TTL judged against a ``now`` handed
in is one a test can stand on either side of without waiting an hour.

The two claims worth reading the file for are the ones that were escalation-path decisions:
an abandoned intent can still be confirmed by a late webhook, and an intent cannot be
abandoned without the gateway's answer in hand.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from billing.domain import (
    DEFAULT_INTENT_TTL,
    GatewayStatus,
    GatewayVerification,
    InvalidPaymentIntentError,
    Money,
    PaymentIntent,
    PaymentIntentAbandoned,
    PaymentIntentAlreadyResolved,
    PaymentIntentConfirmed,
    PaymentIntentFailed,
    PaymentIntentFinalError,
    PaymentIntentStatus,
)

REFERENCE = "psk-ref-0001"
APPLICANT_ID = "app-0001"

NINE_THIRTY = datetime(2026, 8, 1, 9, 30)
TEN_THIRTY = NINE_THIRTY + timedelta(hours=1)
NOON = datetime(2026, 8, 1, 12, 0)

ASKED_FOR = Money(Decimal("100000"))


def an_intent(**overrides: object) -> PaymentIntent:
    fields: dict[str, object] = {
        "reference": REFERENCE,
        "party_id": APPLICANT_ID,
        "amount": ASKED_FOR,
        "initiated_at": NINE_THIRTY,
    }
    fields.update(overrides)
    return PaymentIntent.initiate(**fields)  # type: ignore[arg-type]


def a_verification(**overrides: object) -> GatewayVerification:
    fields: dict[str, object] = {"reference": REFERENCE, "status": GatewayStatus.UNKNOWN}
    fields.update(overrides)
    return GatewayVerification(**fields)  # type: ignore[arg-type]


class TestOpening:
    def test_a_new_intent_is_initiated_and_has_confirmed_nothing(self) -> None:
        intent = an_intent()

        assert intent.status is PaymentIntentStatus.INITIATED
        assert intent.is_open
        assert intent.is_final is False
        assert intent.confirmed_amount is None
        assert intent.resolved_at is None
        assert intent.failure_reason is None

    def test_the_ttl_defaults_to_billings_own(self) -> None:
        assert an_intent().ttl == DEFAULT_INTENT_TTL
        assert an_intent().expires_at == NINE_THIRTY + DEFAULT_INTENT_TTL

    def test_a_ttl_is_a_construction_argument(self) -> None:
        assert an_intent(ttl=timedelta(minutes=15)).expires_at == NINE_THIRTY + timedelta(
            minutes=15
        )

    @pytest.mark.parametrize("ttl", [timedelta(0), timedelta(seconds=-1)], ids=["zero", "negative"])
    def test_a_ttl_that_expires_immediately_is_refused(self, ttl: timedelta) -> None:
        with pytest.raises(InvalidPaymentIntentError):
            an_intent(ttl=ttl)

    def test_an_intent_for_nothing_is_refused(self) -> None:
        with pytest.raises(InvalidPaymentIntentError):
            an_intent(amount=Money.zero())

    @pytest.mark.parametrize("blank", ["", "   "], ids=["empty", "whitespace"])
    def test_a_blank_reference_is_refused(self, blank: str) -> None:
        with pytest.raises(Exception):  # noqa: B017 - MissingIdentifierError, a BillingError
            an_intent(reference=blank)


class TestExpiry:
    """The TTL selects a question for the gateway. It never answers one."""

    def test_an_intent_inside_its_ttl_has_not_expired(self) -> None:
        assert an_intent().has_expired(NINE_THIRTY + timedelta(minutes=59)) is False

    def test_an_intent_at_exactly_its_expiry_has_not_expired(self) -> None:
        """It has used all the time it was given and not one instant more."""
        intent = an_intent()
        assert intent.has_expired(intent.expires_at) is False

    def test_an_intent_one_microsecond_past_its_expiry_has(self) -> None:
        intent = an_intent()
        assert intent.has_expired(intent.expires_at + timedelta(microseconds=1)) is True

    def test_an_answered_intent_is_never_stale(self) -> None:
        """Confirmed, failed or abandoned, the question has been asked. Nothing to chase."""
        confirmed = an_intent()
        confirmed.confirm(amount=ASKED_FOR, at=TEN_THIRTY)

        failed = an_intent()
        failed.fail("declined", at=TEN_THIRTY)

        abandoned = an_intent()
        abandoned.abandon(verified=a_verification(), at=TEN_THIRTY)

        for intent in (confirmed, failed, abandoned):
            assert intent.has_expired(NOON) is False


class TestConfirming:
    def test_confirming_records_the_gateways_amount_and_the_instant(self) -> None:
        intent = an_intent()

        outcome = intent.confirm(amount=Money(Decimal("100000")), at=TEN_THIRTY)

        assert isinstance(outcome, PaymentIntentConfirmed)
        assert outcome.changed is True
        assert outcome.amount_matched is True
        assert outcome.was_revived is False
        assert intent.status is PaymentIntentStatus.CONFIRMED
        assert intent.confirmed_amount == Money("100000")
        assert intent.resolved_at == TEN_THIRTY
        assert intent.is_final

    def test_a_short_payment_confirms_the_intent_and_says_so(self) -> None:
        """CLAUDE.md section 3: "intent confirmed" never implies "charge settled"."""
        intent = an_intent()

        outcome = intent.confirm(amount=Money(Decimal("60000")), at=TEN_THIRTY)

        assert isinstance(outcome, PaymentIntentConfirmed)
        assert outcome.amount_matched is False
        assert intent.status is PaymentIntentStatus.CONFIRMED
        assert intent.confirmed_amount == Money("60000")
        assert intent.amount == Money("100000"), "what was asked for is not overwritten"

    def test_an_overpayment_confirms_too(self) -> None:
        outcome = an_intent().confirm(amount=Money(Decimal("150000")), at=TEN_THIRTY)

        assert isinstance(outcome, PaymentIntentConfirmed)
        assert outcome.amount_matched is False

    def test_confirming_twice_changes_nothing(self) -> None:
        """The retrying webhook. Not an error, exactly as a duplicate gateway_ref is not."""
        intent = an_intent()
        intent.confirm(amount=ASKED_FOR, at=TEN_THIRTY)

        outcome = intent.confirm(amount=ASKED_FOR, at=NOON)

        assert isinstance(outcome, PaymentIntentAlreadyResolved)
        assert outcome.changed is False
        assert intent.resolved_at == TEN_THIRTY, "the first confirmation stands"

    def test_a_replay_quoting_a_different_amount_is_still_ignored(self) -> None:
        """The reference is the identity of the movement of money, as it is on the ledger."""
        intent = an_intent()
        intent.confirm(amount=Money(Decimal("100000")), at=TEN_THIRTY)

        outcome = intent.confirm(amount=Money(Decimal("1")), at=NOON)

        assert isinstance(outcome, PaymentIntentAlreadyResolved)
        assert intent.confirmed_amount == Money("100000")

    def test_a_failed_intent_refuses_confirmation(self) -> None:
        """A gateway contradicting itself is a human's problem, not a transition."""
        intent = an_intent()
        intent.fail("insufficient funds", at=TEN_THIRTY)

        with pytest.raises(PaymentIntentFinalError):
            intent.confirm(amount=ASKED_FOR, at=NOON)

    def test_a_confirmed_amount_must_be_money(self) -> None:
        with pytest.raises(InvalidPaymentIntentError):
            an_intent().confirm(amount=Decimal("100000"), at=TEN_THIRTY)  # type: ignore[arg-type]


class TestTheLateWebhook:
    """An abandonment is a presumption. A confirmation is a fact. Facts win."""

    def test_an_abandoned_intent_can_still_be_confirmed(self) -> None:
        intent = an_intent()
        intent.abandon(verified=a_verification(), at=TEN_THIRTY)

        outcome = intent.confirm(amount=Money(Decimal("100000")), at=NOON)

        assert isinstance(outcome, PaymentIntentConfirmed)
        assert outcome.was_revived is True
        assert intent.status is PaymentIntentStatus.CONFIRMED
        assert intent.resolved_at == NOON

    def test_abandoned_is_not_a_final_status(self) -> None:
        intent = an_intent()
        intent.abandon(verified=a_verification(), at=TEN_THIRTY)

        assert intent.is_final is False

    @pytest.mark.parametrize("status", [PaymentIntentStatus.CONFIRMED, PaymentIntentStatus.FAILED])
    def test_confirmed_and_failed_are_final(self, status: PaymentIntentStatus) -> None:
        intent = an_intent()
        if status is PaymentIntentStatus.CONFIRMED:
            intent.confirm(amount=ASKED_FOR, at=TEN_THIRTY)
        else:
            intent.fail("declined", at=TEN_THIRTY)

        assert intent.is_final is True


class TestFailing:
    def test_failing_records_the_reason_and_touches_no_amount(self) -> None:
        intent = an_intent()

        outcome = intent.fail("insufficient funds", at=TEN_THIRTY)

        assert isinstance(outcome, PaymentIntentFailed)
        assert outcome.reason == "insufficient funds"
        assert intent.status is PaymentIntentStatus.FAILED
        assert intent.failure_reason == "insufficient funds"
        assert intent.confirmed_amount is None

    def test_failing_twice_changes_nothing(self) -> None:
        intent = an_intent()
        intent.fail("insufficient funds", at=TEN_THIRTY)

        outcome = intent.fail("something else", at=NOON)

        assert isinstance(outcome, PaymentIntentAlreadyResolved)
        assert intent.failure_reason == "insufficient funds"

    def test_an_abandoned_intent_may_be_failed(self) -> None:
        """A stated fact replacing a presumption is an improvement."""
        intent = an_intent()
        intent.abandon(verified=a_verification(), at=TEN_THIRTY)

        outcome = intent.fail("the card was declined", at=NOON)

        assert isinstance(outcome, PaymentIntentFailed)
        assert intent.status is PaymentIntentStatus.FAILED

    def test_a_confirmed_intent_refuses_to_fail(self) -> None:
        intent = an_intent()
        intent.confirm(amount=ASKED_FOR, at=TEN_THIRTY)

        with pytest.raises(PaymentIntentFinalError):
            intent.fail("changed our mind", at=NOON)

    def test_a_failure_needs_a_reason(self) -> None:
        with pytest.raises(Exception):  # noqa: B017 - MissingIdentifierError, a BillingError
            an_intent().fail("  ", at=TEN_THIRTY)


class TestAbandoning:
    """Verification is a required argument, so "verify first" is not skippable."""

    def test_abandoning_records_the_evidence_it_rests_on(self) -> None:
        intent = an_intent()
        verification = a_verification()

        outcome = intent.abandon(verified=verification, at=TEN_THIRTY)

        assert isinstance(outcome, PaymentIntentAbandoned)
        assert outcome.verified is verification
        assert intent.status is PaymentIntentStatus.ABANDONED
        assert intent.resolved_at == TEN_THIRTY

    def test_an_intent_cannot_be_abandoned_without_asking_the_gateway(self) -> None:
        with pytest.raises(InvalidPaymentIntentError):
            an_intent().abandon(verified=None, at=TEN_THIRTY)  # type: ignore[arg-type]

    def test_a_gateway_reporting_payment_refuses_abandonment(self) -> None:
        """The stuck state the whole mechanism exists to catch, refused at the aggregate."""
        paid = a_verification(status=GatewayStatus.SUCCESS, amount=ASKED_FOR)

        with pytest.raises(InvalidPaymentIntentError, match="paid"):
            an_intent().abandon(verified=paid, at=TEN_THIRTY)

    def test_a_gateway_still_processing_refuses_abandonment(self) -> None:
        """PENDING is not an answer, and writing off a payment in flight is the mistake."""
        pending = a_verification(status=GatewayStatus.PENDING)

        with pytest.raises(InvalidPaymentIntentError, match="still processing"):
            an_intent().abandon(verified=pending, at=TEN_THIRTY)

    def test_evidence_about_another_reference_proves_nothing(self) -> None:
        someone_else = a_verification(reference="psk-ref-9999")

        with pytest.raises(InvalidPaymentIntentError, match="not for intent"):
            an_intent().abandon(verified=someone_else, at=TEN_THIRTY)

    def test_abandoning_twice_changes_nothing(self) -> None:
        """A sweep that runs twice is free."""
        intent = an_intent()
        intent.abandon(verified=a_verification(), at=TEN_THIRTY)

        outcome = intent.abandon(verified=a_verification(), at=NOON)

        assert isinstance(outcome, PaymentIntentAlreadyResolved)
        assert intent.resolved_at == TEN_THIRTY

    @pytest.mark.parametrize("resolve", ["confirm", "fail"])
    def test_a_final_intent_refuses_abandonment(self, resolve: str) -> None:
        intent = an_intent()
        if resolve == "confirm":
            intent.confirm(amount=ASKED_FOR, at=TEN_THIRTY)
        else:
            intent.fail("declined", at=TEN_THIRTY)

        with pytest.raises(PaymentIntentFinalError):
            intent.abandon(verified=a_verification(), at=NOON)


class TestGatewayVerification:
    def test_a_success_without_an_amount_is_refused(self) -> None:
        """There would be nothing to record, and the intent's amount must never be assumed."""
        with pytest.raises(InvalidPaymentIntentError, match="without an amount"):
            GatewayVerification(reference=REFERENCE, status=GatewayStatus.SUCCESS)

    def test_only_pending_is_inconclusive(self) -> None:
        assert a_verification(status=GatewayStatus.PENDING).is_conclusive is False
        assert a_verification(status=GatewayStatus.UNKNOWN).is_conclusive is True
        assert a_verification(status=GatewayStatus.FAILED).is_conclusive is True

    def test_an_amount_must_be_money(self) -> None:
        with pytest.raises(InvalidPaymentIntentError):
            a_verification(status=GatewayStatus.FAILED, amount=Decimal("1"))
