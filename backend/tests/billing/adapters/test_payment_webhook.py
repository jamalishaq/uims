"""The gateway webhook: signature first, then everything else.

CLAUDE.md section 3 requires this adapter to "verify the gateway signature before the payload
reaches any use case", and section 4 marks the path as one a human reviews line by line. These
tests are the executable half of that review, and the three the phase was specified against
are :class:`TestSignature`, :class:`TestReplay` and :class:`TestAmountMismatch`.

The sharpest of them is
:meth:`TestSignature.test_a_body_that_is_not_even_json_is_rejected_as_a_bad_signature`. Every
other ordering test can be satisfied by an implementation that parses first and checks
afterwards, as long as it does not *act* on the parse. That one cannot: a body that would
crash a parser is rejected as a signature failure, which is only possible if the parser was
never reached.
"""

import hmac
import json
from datetime import datetime
from decimal import Decimal

import pytest

from billing.adapters.inbound import (
    MalformedWebhookError,
    PaymentWebhookHandler,
    WebhookSignatureError,
    WebhookSignatureVerifier,
)
from billing.adapters.outbound import InMemoryEventPublisher
from billing.application import PaymentIntentNotFoundError
from billing.domain import (
    AcceptanceFeePaid,
    Account,
    ChargeKind,
    Money,
    PaymentIntent,
    PaymentIntentFinalError,
    PaymentIntentStatus,
)
from billing.ports import AccountRepositoryPort, PaymentIntentRepositoryPort

WEBHOOK_SECRET = "sk_test_not_a_real_key"
"""The same test secret ``conftest`` builds the verifier with, checked against it below."""

APPLICANT_ID = "app-0001"
PROGRAM_ID = "prog-csc-bsc"
SESSION_2026 = "sess-2026"

ACCEPTANCE_REF = "psk-ref-acceptance"
SESSION_REF = "psk-ref-session"

JULY = datetime(2026, 7, 1, 9, 30)
PAID_AT = "2026-07-01T10:30:00"


def a_payload(**overrides: object) -> dict[str, object]:
    """A Paystack ``charge.success`` for the acceptance fee: ₦20,000, quoted in kobo."""
    data: dict[str, object] = {
        "reference": ACCEPTANCE_REF,
        "amount": 2_000_000,
        "status": "success",
        "paid_at": PAID_AT,
        "customer": {"email": "someone@example.com"},
    }
    data.update(overrides.pop("data", {}))  # type: ignore[arg-type]
    payload: dict[str, object] = {"event": "charge.success", "data": data}
    payload.update(overrides)
    return payload


def body_of(payload: dict[str, object]) -> bytes:
    return json.dumps(payload).encode("utf-8")


def sign(raw_body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """The signature Paystack would send: HMAC-SHA512 over the raw body, hex-encoded.

    Written out here rather than taken from the verifier on purpose. A test that asked the
    thing under test to compute the expected answer would pass just as happily if both sides
    were wrong together — which is why this spells out ``hmac``, ``sha512`` and ``hexdigest``
    instead of reaching for the object under test.
    """
    return hmac.new(secret.encode("utf-8"), raw_body, "sha512").hexdigest()


def test_this_modules_secret_is_the_one_the_handler_was_built_with(webhook_secret: str) -> None:
    """Guard: if these drifted apart, every signature test above would pass vacuously.

    The correctly-signed cases would fail, so the drift would be caught — but the *rejection*
    cases would then be rejecting for the wrong reason, and a webhook that verified nothing
    would still look green.
    """
    assert webhook_secret == WEBHOOK_SECRET


@pytest.fixture
def an_admitted_account(accounts: AccountRepositoryPort) -> Account:
    """What ``OfferAccepted`` leaves behind: 20,000 gating and 50,000 not."""
    account = Account.open(APPLICANT_ID, PROGRAM_ID)
    account.raise_acceptance_fee(SESSION_2026, Money("20000"))
    account.raise_matriculation_fee(SESSION_2026, Money("50000"))
    accounts.add(account)
    return account


@pytest.fixture
def an_open_intent(
    an_admitted_account: Account, intents: PaymentIntentRepositoryPort
) -> PaymentIntent:
    """A checkout for the acceptance fee, opened and awaiting the gateway."""
    intent = PaymentIntent.initiate(
        reference=ACCEPTANCE_REF,
        party_id=APPLICANT_ID,
        amount=Money("20000"),
        initiated_at=JULY,
    )
    intents.add(intent)
    return intent


class TestSignature:
    """Nothing gets past this, and nothing happens on the way to being refused."""

    def test_a_correctly_signed_request_is_accepted(
        self,
        payment_webhook: PaymentWebhookHandler,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
    ) -> None:
        body = body_of(a_payload())

        result = payment_webhook.handle(body, sign(body))

        assert result is not None
        assert an_admitted_account.total_paid == Money("20000")

    def test_a_forged_signature_is_rejected_with_no_side_effects(
        self,
        payment_webhook: PaymentWebhookHandler,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
        events: InMemoryEventPublisher,
    ) -> None:
        body = body_of(a_payload())

        with pytest.raises(WebhookSignatureError):
            payment_webhook.handle(body, "0" * 128)

        assert an_admitted_account.payments == (), "no money reached the ledger"
        assert an_admitted_account.total_paid == Money.zero()
        assert an_open_intent.status is PaymentIntentStatus.INITIATED, "the intent did not move"
        assert events.published == (), "nothing was announced"

    def test_a_body_altered_after_signing_is_rejected(
        self, payment_webhook: PaymentWebhookHandler, an_open_intent: PaymentIntent
    ) -> None:
        """The attack this exists to stop: sign ₦20,000, deliver ₦2,000,000."""
        honest = body_of(a_payload())
        signature = sign(honest)
        tampered = body_of(a_payload(data={"amount": 200_000_000}))

        with pytest.raises(WebhookSignatureError):
            payment_webhook.handle(tampered, signature)

        assert an_open_intent.status is PaymentIntentStatus.INITIATED

    @pytest.mark.parametrize("signature", [None, "", "   "], ids=["absent", "empty", "blank"])
    def test_a_missing_signature_is_a_rejection_and_not_a_skip(
        self, payment_webhook: PaymentWebhookHandler, signature: str | None
    ) -> None:
        with pytest.raises(WebhookSignatureError):
            payment_webhook.handle(body_of(a_payload()), signature)

    def test_a_signature_from_the_wrong_secret_is_rejected(
        self, payment_webhook: PaymentWebhookHandler
    ) -> None:
        body = body_of(a_payload())

        with pytest.raises(WebhookSignatureError):
            payment_webhook.handle(body, sign(body, secret="sk_test_someone_elses_key"))

    def test_a_body_that_is_not_even_json_is_rejected_as_a_bad_signature(
        self, payment_webhook: PaymentWebhookHandler
    ) -> None:
        """**The ordering test.** If verification ever moved after the parse, this goes red.

        A ``JSONDecodeError`` here — or a ``MalformedWebhookError`` — would mean the body had
        been handed to a parser before anybody established the request was from the gateway.
        """
        with pytest.raises(WebhookSignatureError):
            payment_webhook.handle(b"\x00 not json at all {{{", "0" * 128)

    def test_a_correctly_signed_body_that_is_not_json_is_malformed_rather_than_forged(
        self, payment_webhook: PaymentWebhookHandler
    ) -> None:
        """The other half of the pair: past the signature, the parser is reached after all."""
        body = b"not json at all {{{"

        with pytest.raises(MalformedWebhookError):
            payment_webhook.handle(body, sign(body))

    def test_the_verifier_refuses_an_empty_secret(self) -> None:
        """An empty secret verifies nothing while looking exactly like verification."""
        with pytest.raises(ValueError, match="secret"):
            WebhookSignatureVerifier("")

    def test_the_verifier_refuses_a_body_that_is_not_raw_bytes(
        self, verifier: WebhookSignatureVerifier
    ) -> None:
        """A ``str`` would have to be encoded to be hashed, and that choice is the gap."""
        with pytest.raises(TypeError):
            verifier.verify(json.dumps(a_payload()), "0" * 128)  # type: ignore[arg-type]

    def test_the_header_and_digest_are_construction_arguments(self) -> None:
        """A second gateway is a second construction, not a second code path."""
        verifier = WebhookSignatureVerifier("s3cret", header="x-other-signature", digest="sha256")
        body = b'{"event":"charge.success"}'

        assert verifier.header == "x-other-signature"
        verifier.verify(body, hmac.new(b"s3cret", body, "sha256").hexdigest())


class TestReplay:
    """At-least-once delivery is what every gateway worth using does."""

    def test_a_replayed_webhook_is_a_no_op(
        self,
        payment_webhook: PaymentWebhookHandler,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
        events: InMemoryEventPublisher,
    ) -> None:
        body = body_of(a_payload())
        signature = sign(body)

        first = payment_webhook.handle(body, signature)
        second = payment_webhook.handle(body, signature)

        assert first is not None and second is not None
        assert first.was_replay is False
        assert second.was_replay is True
        assert len(an_admitted_account.payments) == 1, "one payment on the ledger"
        assert an_admitted_account.total_paid == Money("20000")
        assert an_open_intent.status is PaymentIntentStatus.CONFIRMED

    def test_the_gating_charge_is_announced_exactly_once(
        self,
        payment_webhook: PaymentWebhookHandler,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
        events: InMemoryEventPublisher,
    ) -> None:
        body = body_of(a_payload())
        signature = sign(body)

        payment_webhook.handle(body, signature)
        payment_webhook.handle(body, signature)
        payment_webhook.handle(body, signature)

        assert events.published == (AcceptanceFeePaid(applicant_id=APPLICANT_ID),)

    def test_five_deliveries_leave_the_same_balances_as_one(
        self,
        payment_webhook: PaymentWebhookHandler,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
    ) -> None:
        body = body_of(a_payload())
        signature = sign(body)

        for _ in range(5):
            payment_webhook.handle(body, signature)

        assert an_admitted_account.total_paid == Money("20000")
        assert an_admitted_account.outstanding == Money("50000"), "the matriculation fee only"
        assert an_admitted_account.credit_balance == Money.zero()


class TestAmountMismatch:
    """The ledger records what the gateway confirms, never what the intent asked for."""

    @pytest.fixture
    def a_session_bill(
        self, accounts: AccountRepositoryPort, intents: PaymentIntentRepositoryPort
    ) -> Account:
        """One 100,000 session charge and a checkout opened for the whole of it."""
        account = Account.open("app-0002", PROGRAM_ID)
        account.raise_session_fee(SESSION_2026, Money("100000"))
        accounts.add(account)
        intents.add(
            PaymentIntent.initiate(
                reference=SESSION_REF,
                party_id="app-0002",
                amount=Money("100000"),
                initiated_at=JULY,
            )
        )
        return account

    def test_a_short_payment_credits_what_arrived_and_leaves_the_charge_unsettled(
        self,
        payment_webhook: PaymentWebhookHandler,
        a_session_bill: Account,
        intents: PaymentIntentRepositoryPort,
    ) -> None:
        body = body_of(
            a_payload(data={"reference": SESSION_REF, "amount": 6_000_000})
        )  # ₦60,000 against a ₦100,000 intent

        result = payment_webhook.handle(body, sign(body))

        assert result is not None
        assert result.amount_matched is False

        charge = a_session_bill.charge_for(ChargeKind.SESSION, SESSION_2026)
        assert charge is not None
        assert a_session_bill.total_paid == Money("60000"), "the confirmed amount, not the intent's"
        assert charge.allocated == Money("60000")
        assert charge.is_settled is False
        assert a_session_bill.outstanding == Money("40000")

        intent = intents.get(SESSION_REF)
        assert intent is not None
        assert intent.status is PaymentIntentStatus.CONFIRMED, "confirmed, but not settled"
        assert intent.amount == Money("100000"), "what was asked for is still on record"
        assert intent.confirmed_amount == Money("60000")

    def test_an_overpayment_becomes_a_credit_balance(
        self, payment_webhook: PaymentWebhookHandler, a_session_bill: Account
    ) -> None:
        """Surplus is legal; never assume balance <= charges."""
        body = body_of(a_payload(data={"reference": SESSION_REF, "amount": 12_000_000}))

        result = payment_webhook.handle(body, sign(body))

        assert result is not None and result.amount_matched is False
        assert a_session_bill.outstanding == Money.zero()
        assert a_session_bill.credit_balance == Money("20000")


class TestPayloadTranslation:
    def test_an_unknown_event_is_ignored_without_touching_anything(
        self, payment_webhook: PaymentWebhookHandler, an_open_intent: PaymentIntent
    ) -> None:
        """Reconciliation is the safety net that makes silence the safe answer."""
        body = body_of(a_payload(event="charge.dispute.create"))

        assert payment_webhook.handle(body, sign(body)) is None
        assert an_open_intent.status is PaymentIntentStatus.INITIATED

    def test_a_reported_failure_moves_the_intent_and_not_the_ledger(
        self,
        payment_webhook: PaymentWebhookHandler,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
        events: InMemoryEventPublisher,
    ) -> None:
        body = body_of(a_payload(event="charge.failed"))

        result = payment_webhook.handle(body, sign(body))

        assert result is not None
        assert result.ledger_outcome is None, "the ledger was not consulted"
        assert an_admitted_account.payments == ()
        assert an_admitted_account.outstanding == Money("70000"), "nothing was settled"
        assert events.published == ()
        assert an_open_intent.status is PaymentIntentStatus.FAILED

    def test_a_failure_the_gateway_later_contradicts_still_banks_the_money(
        self,
        payment_webhook: PaymentWebhookHandler,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
    ) -> None:
        """Money that moved is recorded whatever the intent says; the contradiction raises.

        The webhook-seam view of ``ConfirmPayment``'s ledger-first ordering. Only reachable
        when the gateway states two different things about one reference — a plain reported
        failure never touches the ledger, which the test above holds.
        """
        failed = body_of(a_payload(event="charge.failed"))
        payment_webhook.handle(failed, sign(failed))

        succeeded = body_of(a_payload())
        with pytest.raises(PaymentIntentFinalError):
            payment_webhook.handle(succeeded, sign(succeeded))

        assert an_admitted_account.total_paid == Money("20000")

    def test_kobo_becomes_naira_exactly(
        self,
        payment_webhook: PaymentWebhookHandler,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
    ) -> None:
        body = body_of(a_payload(data={"amount": 2_000_050}))

        payment_webhook.handle(body, sign(body))

        assert an_admitted_account.total_paid == Money(Decimal("20000.50"))

    def test_a_fractional_kobo_amount_is_refused(
        self, payment_webhook: PaymentWebhookHandler, an_open_intent: PaymentIntent
    ) -> None:
        """A JSON number with a decimal point parses as a float, and a float is not money."""
        body = body_of(a_payload(data={"amount": 2_000_000.5}))

        with pytest.raises(MalformedWebhookError, match="whole number of kobo"):
            payment_webhook.handle(body, sign(body))

    def test_the_gateways_timestamp_is_what_the_ledger_records(
        self,
        payment_webhook: PaymentWebhookHandler,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
    ) -> None:
        body = body_of(a_payload())

        payment_webhook.handle(body, sign(body))

        assert an_admitted_account.payments[0].received_at == datetime(2026, 7, 1, 10, 30)

    def test_an_offset_carrying_timestamp_keeps_its_offset(
        self,
        payment_webhook: PaymentWebhookHandler,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
    ) -> None:
        """Normalising it is the sort of helpfulness that dates an entry an hour out."""
        body = body_of(a_payload(data={"paid_at": "2026-07-01T10:30:00.000+01:00"}))

        payment_webhook.handle(body, sign(body))

        recorded = an_admitted_account.payments[0].received_at
        assert recorded.utcoffset() is not None
        assert recorded.isoformat() == "2026-07-01T10:30:00+01:00"

    @pytest.mark.parametrize(
        ("field", "value"),
        [("reference", ""), ("reference", None), ("paid_at", None), ("amount", "2000000")],
        ids=["blank-reference", "no-reference", "no-timestamp", "amount-as-string"],
    )
    def test_a_signed_charge_this_cannot_read_is_malformed(
        self, payment_webhook: PaymentWebhookHandler, field: str, value: object
    ) -> None:
        """A separate failure from a bad signature: this is the gateway, sending nonsense."""
        data: dict[str, object] = {
            "reference": ACCEPTANCE_REF,
            "amount": 2_000_000,
            "paid_at": PAID_AT,
        }
        if value is None:
            del data[field]
        else:
            data[field] = value
        body = body_of({"event": "charge.success", "data": data})

        with pytest.raises(MalformedWebhookError):
            payment_webhook.handle(body, sign(body))

    def test_a_charge_with_no_data_object_is_malformed(
        self, payment_webhook: PaymentWebhookHandler
    ) -> None:
        body = body_of({"event": "charge.success"})

        with pytest.raises(MalformedWebhookError):
            payment_webhook.handle(body, sign(body))


class TestUnsolicitedReferences:
    def test_a_signed_charge_for_a_reference_we_never_issued_is_refused(
        self, payment_webhook: PaymentWebhookHandler, an_admitted_account: Account
    ) -> None:
        """A valid signature says who sent it, not whose money it is."""
        body = body_of(a_payload(data={"reference": "psk-ref-nobody-opened"}))

        with pytest.raises(PaymentIntentNotFoundError):
            payment_webhook.handle(body, sign(body))

        assert an_admitted_account.payments == ()

    def test_the_party_comes_from_the_intent_and_not_the_payload(
        self,
        payment_webhook: PaymentWebhookHandler,
        an_open_intent: PaymentIntent,
        an_admitted_account: Account,
        accounts: AccountRepositoryPort,
    ) -> None:
        """A payload naming somebody else's ledger credits the intent's party regardless."""
        somebody_else = Account.open("app-9999", PROGRAM_ID)
        somebody_else.raise_acceptance_fee(SESSION_2026, Money("20000"))
        accounts.add(somebody_else)
        body = body_of(a_payload(data={"party_id": "app-9999", "customer": {"id": "app-9999"}}))

        payment_webhook.handle(body, sign(body))

        assert an_admitted_account.total_paid == Money("20000")
        assert somebody_else.total_paid == Money.zero()
