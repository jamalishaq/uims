"""Billing over HTTP, including the webhook.

``tests/billing/adapters/test_payment_webhook.py`` already pins the handler's behaviour in 499
lines and is not touched. What is new here is the *transport*: that the route hands the handler
the raw bytes rather than a re-serialised dict, that it reads the header the handler names, and
that the four ways the handler refuses arrive as four different statuses.

The property worth stating: if the route ever parsed the body before verifying it, the tamper
test below goes green-to-red immediately, because the bytes the HMAC covers would no longer be
the bytes that arrived.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from tests.http.conftest import WEBHOOK_SECRET

from billing.adapters.inbound.payment_webhook import PAYSTACK_SIGNATURE_HEADER
from billing.domain.account import Account
from billing.domain.charge import ChargeKind
from billing.domain.values import Money

WEBHOOK_PATH = "/billing/webhooks/paystack"


def _sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha512).hexdigest()


def _charge_success(reference: str = "ref-1", *, kobo: int = 2_000_000) -> bytes:
    """A Paystack ``charge.success``, serialised exactly once.

    The bytes are built here and never rebuilt, because the signature covers *these* bytes.
    Re-serialising the dict to sign it would be the bug this file exists to catch.
    """
    return json.dumps(
        {
            "event": "charge.success",
            "data": {
                "reference": reference,
                "amount": kobo,
                "paid_at": "2026-09-01T10:00:00+00:00",
            },
        }
    ).encode("utf-8")


async def _seed_account_and_intent(client: AsyncClient, api: str, repos, reference="ref-1") -> None:
    account = Account.open("stu-1", "prog-csc")
    account.raise_charge(ChargeKind.SESSION, "sess-2026", Money(Decimal("100000.00")))
    await repos.accounts().add(account)

    response = await client.post(
        f"{api}/billing/payment-intents",
        json={
            "party_id": "stu-1",
            "reference": reference,
            "amount": "20000.00",
            "initiated_at": "2026-09-01T09:00:00+00:00",
        },
    )
    assert response.status_code == 201, response.text


class TestTheWebhookIsVerifiedFirst:
    async def test_a_correctly_signed_charge_is_confirmed(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_account_and_intent(client, api, repos)
        body = _charge_success()

        response = await client.post(
            f"{api}{WEBHOOK_PATH}",
            content=body,
            headers={PAYSTACK_SIGNATURE_HEADER: _sign(body), "content-type": "application/json"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["handled"] is True
        assert response.json()["result"]["intent_outcome"]["outcome"] == "confirmed"
        assert response.json()["result"]["amount_matched"] is True

    async def test_a_forged_signature_is_rejected_with_no_side_effect(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_account_and_intent(client, api, repos)
        body = _charge_success()

        response = await client.post(
            f"{api}{WEBHOOK_PATH}",
            content=body,
            headers={PAYSTACK_SIGNATURE_HEADER: "0" * 128, "content-type": "application/json"},
        )
        assert response.status_code == 401

        ledger = await client.get(f"{api}/billing/accounts/stu-1")
        assert ledger.json()["total_paid"] == "0.00", "nothing was written"

    async def test_a_missing_signature_is_a_rejection_not_a_skip(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_account_and_intent(client, api, repos)
        response = await client.post(
            f"{api}{WEBHOOK_PATH}",
            content=_charge_success(),
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 401

    async def test_a_tampered_body_no_longer_matches_its_signature(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """The load-bearing one: the HMAC must cover the bytes as received, byte for byte."""
        await _seed_account_and_intent(client, api, repos)
        signature = _sign(_charge_success(kobo=2_000_000))

        response = await client.post(
            f"{api}{WEBHOOK_PATH}",
            content=_charge_success(kobo=99_900_000),
            headers={PAYSTACK_SIGNATURE_HEADER: signature, "content-type": "application/json"},
        )
        assert response.status_code == 401

    async def test_a_body_that_is_not_json_is_rejected_as_a_bad_signature(
        self, client: AsyncClient, api: str
    ) -> None:
        """If verification ever moved after the parse, this becomes a 400 and goes red."""
        response = await client.post(
            f"{api}{WEBHOOK_PATH}",
            content=b"\x00 not json at all {{{",
            headers={PAYSTACK_SIGNATURE_HEADER: "0" * 128},
        )
        assert response.status_code == 401
        assert response.json()["error"] == "WebhookSignatureError"

    async def test_a_signed_body_that_is_not_json_is_a_400(
        self, client: AsyncClient, api: str
    ) -> None:
        """Signed and unreadable is the gateway misbehaving — a different thing from a stranger."""
        body = b"not json at all {{{"
        response = await client.post(
            f"{api}{WEBHOOK_PATH}",
            content=body,
            headers={PAYSTACK_SIGNATURE_HEADER: _sign(body)},
        )
        assert response.status_code == 400
        assert response.json()["error"] == "MalformedWebhookError"

    async def test_the_rejection_says_nothing_useful(self, client: AsyncClient, api: str) -> None:
        """An error message is an oracle if it is specific enough."""
        body = _charge_success()
        response = await client.post(
            f"{api}{WEBHOOK_PATH}",
            content=body,
            headers={PAYSTACK_SIGNATURE_HEADER: "0" * 128},
        )
        detail = response.json()["detail"]
        assert _sign(body) not in detail
        assert "128" not in detail and "length" not in detail.lower()


class TestWhatTheWebhookIgnores:
    async def test_an_event_this_context_has_no_opinion_about_is_a_no_op(
        self, client: AsyncClient, api: str
    ) -> None:
        body = json.dumps({"event": "charge.dispute.create", "data": {}}).encode("utf-8")
        response = await client.post(
            f"{api}{WEBHOOK_PATH}", content=body, headers={PAYSTACK_SIGNATURE_HEADER: _sign(body)}
        )
        assert response.status_code == 200
        assert response.json() == {"handled": False, "result": None}

    async def test_a_reference_this_university_never_issued_is_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        body = _charge_success(reference="never-issued")
        response = await client.post(
            f"{api}{WEBHOOK_PATH}", content=body, headers={PAYSTACK_SIGNATURE_HEADER: _sign(body)}
        )
        assert response.status_code == 404
        assert response.json()["error"] == "PaymentIntentNotFoundError"


class TestReplayAndMismatch:
    async def test_a_replayed_webhook_changes_the_ledger_once(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_account_and_intent(client, api, repos)
        body = _charge_success()
        headers = {PAYSTACK_SIGNATURE_HEADER: _sign(body)}

        first = await client.post(f"{api}{WEBHOOK_PATH}", content=body, headers=headers)
        second = await client.post(f"{api}{WEBHOOK_PATH}", content=body, headers=headers)

        assert first.json()["result"]["was_replay"] is False
        assert second.json()["result"]["was_replay"] is True

        ledger = await client.get(f"{api}/billing/accounts/stu-1")
        assert ledger.json()["total_paid"] == "20000.00", "one payment, not two"

    async def test_a_short_payment_confirms_the_intent_and_leaves_the_charge_outstanding(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """Both are true at once, and neither is refused."""
        await _seed_account_and_intent(client, api, repos)
        body = _charge_success(kobo=1_000_000)

        response = await client.post(
            f"{api}{WEBHOOK_PATH}", content=body, headers={PAYSTACK_SIGNATURE_HEADER: _sign(body)}
        )
        assert response.status_code == 200
        assert response.json()["result"]["amount_matched"] is False

        ledger = await client.get(f"{api}/billing/accounts/stu-1")
        assert ledger.json()["total_paid"] == "10000.00"
        assert ledger.json()["outstanding"] == "90000.00"


class TestTheLedgerRoutes:
    async def test_a_party_with_no_ledger_is_a_404(self, client: AsyncClient, api: str) -> None:
        response = await client.get(f"{api}/billing/accounts/nobody")
        assert response.status_code == 404
        assert response.json()["error"] == "AccountNotFoundError"

    async def test_money_crosses_as_a_string_with_two_places(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """A float would put back the imprecision ``Money`` refuses at construction."""
        account = Account.open("stu-1", "prog-csc")
        account.raise_charge(ChargeKind.SESSION, "sess-2026", Money(Decimal("100000.10")))
        await repos.accounts().add(account)

        response = await client.get(f"{api}/billing/accounts/stu-1")
        assert response.json()["charges"][0]["amount"] == "100000.10"
        assert isinstance(response.json()["total_charged"], str)

    async def test_a_matric_number_can_be_linked_and_then_resolves(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await repos.accounts().add(Account.open("app-1", "prog-csc"))

        linked = await client.post(
            f"{api}/billing/accounts/app-1/student-link", json={"student_id": "260591001"}
        )
        assert linked.status_code == 200
        assert linked.json()["was_already_linked"] is False

        by_matric = await client.get(f"{api}/billing/accounts/260591001")
        assert by_matric.status_code == 200
        assert by_matric.json()["party_id"] == "app-1"

    async def test_a_bursary_recorded_payment_is_idempotent_on_its_reference(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        account = Account.open("stu-1", "prog-csc")
        account.raise_charge(ChargeKind.SESSION, "sess-2026", Money(Decimal("100000.00")))
        await repos.accounts().add(account)

        payment = {
            "gateway_ref": "bursary-1",
            "amount": "5000.00",
            "received_at": datetime(2026, 9, 1, tzinfo=UTC).isoformat(),
        }
        first = await client.post(f"{api}/billing/accounts/stu-1/payments", json=payment)
        second = await client.post(f"{api}/billing/accounts/stu-1/payments", json=payment)

        assert first.json()["was_duplicate"] is False
        assert second.json()["was_duplicate"] is True
        assert second.json()["outcome"]["outcome"] == "duplicate_ignored"

        ledger = await client.get(f"{api}/billing/accounts/stu-1")
        assert ledger.json()["total_paid"] == "5000.00"

    @pytest.mark.parametrize("amount", ["0", "-10.00"])
    async def test_a_payment_that_moves_no_money_is_refused(
        self, client: AsyncClient, api: str, amount: str
    ) -> None:
        response = await client.post(
            f"{api}/billing/accounts/stu-1/payments",
            json={
                "gateway_ref": "x",
                "amount": amount,
                "received_at": "2026-09-01T00:00:00+00:00",
            },
        )
        assert response.status_code == 422


class TestTheAdminSweeps:
    async def test_applying_session_fees_with_no_schedule_is_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        """An account with no acceptance charge would gate matriculation on nothing."""
        response = await client.post(
            f"{api}/billing/session-fees", json={"session_id": "sess-2026"}
        )
        assert response.status_code == 404
        assert response.json()["error"] == "FeeScheduleNotPublishedError"

    async def test_a_sweep_over_nothing_reports_nothing(
        self, client: AsyncClient, api: str
    ) -> None:
        response = await client.post(
            f"{api}/billing/reconciliations", json={"now": "2026-09-01T12:00:00+00:00"}
        )
        assert response.status_code == 200
        assert response.json()["examined"] == 0
        assert response.json()["recovered_money"] is False
