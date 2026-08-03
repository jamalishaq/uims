"""Inbound adapter: the payment gateway says money moved.

**This is the security-sensitive path.** CLAUDE.md section 3 requires that this adapter
"verify the gateway signature before the payload reaches any use case", and section 4 forbids
generating or refactoring the verification without explicit human review of the diff. The file
is deliberately small and does two things in a fixed order, so that the order can be checked
by reading rather than by reasoning.

The threat is not subtle. This endpoint is public by necessity — a gateway has to be able to
reach it — and anything that can reach it can claim that ₦500,000 arrived. The signature is
the only thing standing between "a stranger posted some JSON" and "the university's bursary
believes a bill is paid", so nothing about the body may be trusted, acted on, or even
*interpreted* before the HMAC matches. That is why :class:`WebhookSignatureVerifier` is a
separate object with no other responsibility and no knowledge of what a payload contains: it
cannot leak a decision into the parse, because it cannot parse.

Six properties, each of which is a way this has gone wrong in real systems:

1. **Verification happens first.** It is the first statement of
   :meth:`PaymentWebhookHandler.handle`; ``json.loads`` is not reachable until it returns.
   A malformed body with a bad signature is rejected as a bad signature, which is what the
   test asserting it holds.
2. **The comparison is** ``hmac.compare_digest``, never ``==``. A byte-by-byte comparison
   that short-circuits leaks the correct digest a character at a time to anybody willing to
   time the responses.
3. **The HMAC covers the raw bytes exactly as they arrived.** Not a re-serialised dict, not a
   stripped string, not a decoded-and-re-encoded one. Any normalisation before hashing is a
   bypass: the attacker signs one document and the system acts on a different one.
4. **A missing signature is a rejection, not a skip.** The absent header is the oldest bypass
   there is.
5. **The secret is a constructor argument.** Nothing in ``src/`` reads an environment
   variable; loading ``PAYSTACK_SECRET_KEY`` is the composition root's job.
6. **Rejections say nothing useful.** No expected digest, no partial match, no "signature was
   the right length" — an error message is an oracle if it is specific enough.

**Everything the payload says about identity is ignored.** The party whose ledger is credited
comes from the ``PaymentIntent`` this system opened, looked up by the reference; the payload's
customer and metadata are never read. A valid signature proves the gateway sent the request.
It does not prove the gateway is right about whose money this is, and it would not survive a
leaked secret if it did.

**Unrecognised events are ignored rather than guessed at.** A gateway emits many things —
disputes, transfers, subscription notices — and this context has an opinion about exactly two.
Ignoring the rest is safe *because* reconciliation exists: anything a webhook fails to deliver
is caught by ``ReconcilePaymentIntents`` asking the gateway directly, so the cost of not
understanding a message is one sweep's delay rather than a lost payment. That safety net is
what makes it possible to be conservative here instead of clever.
"""

import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from billing.application.confirm_payment import (
    ConfirmPayment,
    ConfirmPaymentCommand,
    PaymentConfirmed,
)

PAYSTACK_SIGNATURE_HEADER = "x-paystack-signature"
"""The header Paystack puts its HMAC in. A default, not a law — see the constructor."""

PAYSTACK_DIGEST = "sha512"
"""Paystack signs with HMAC-SHA512 over the raw request body, hex-encoded."""

SUCCESS_EVENTS = frozenset({"charge.success"})
"""Events that mean money moved. Deliberately a set of one."""

FAILURE_EVENTS = frozenset({"charge.failed"})
"""Events that mean an attempt was made and did not work. No money, so no ledger entry."""

KOBO_PER_NAIRA = 100
"""Paystack quotes amounts in the minor unit. So does every gateway worth integrating."""


class PaymentWebhookError(Exception):
    """Base class for every refusal this adapter makes at the boundary."""


class WebhookSignatureError(PaymentWebhookError):
    """The request was not signed by the holder of the shared secret.

    Carries no detail about what was expected. A caller who can tell "wrong length" from
    "wrong bytes" from "wrong encoding" has been handed a way to search for the answer.
    """


class MalformedWebhookError(PaymentWebhookError):
    """The request was genuinely signed, but is not shaped like anything this can act on.

    A separate type from a bad signature on purpose, and it means something entirely
    different: a bad signature is a stranger, and this is the gateway itself sending
    something unexpected — which is an integration bug worth an alert rather than a
    background rate of noise.
    """


class WebhookSignatureVerifier:
    """Checks that a request body was signed with the shared secret. It does nothing else.

    It cannot parse, decode or interpret a payload, and it has no reference to a use case or a
    repository. That is the point of it being its own class: there is no path through this
    object that reaches the rest of the system, so "was the signature checked first" is a
    question about one line in the caller rather than about this file's control flow.
    """

    def __init__(
        self,
        secret: str | bytes,
        *,
        header: str = PAYSTACK_SIGNATURE_HEADER,
        digest: str = PAYSTACK_DIGEST,
    ) -> None:
        """Hold the shared secret, the header to read it from, and the digest to use.

        All three are arguments so that a second gateway is a second *construction* rather
        than a second code path — the arrangement ``ClearanceThresholds`` uses one context
        over. The secret is accepted as ``str`` for the convenience of a config loader and
        encoded once, here, so that no caller has a chance to encode it differently from the
        way the body is hashed.
        """
        if not secret:
            raise ValueError(
                "a webhook signing secret is required; an empty secret would verify nothing "
                "while looking exactly like verification"
            )
        self._secret = secret.encode("utf-8") if isinstance(secret, str) else secret
        self._header = header
        self._digest = digest

    @property
    def header(self) -> str:
        """The header a transport should pull the signature out of."""
        return self._header

    def verify(self, raw_body: bytes, signature: str | None) -> None:
        """Raise unless ``signature`` is this secret's HMAC over exactly these bytes.

        Returns ``None`` on success and raises otherwise, rather than returning a bool: a
        caller who forgets to check a returned bool has a working system that verifies
        nothing, and a caller who forgets to catch an exception has a system that rejects
        everything. Of the two ways to be wrong, only one is safe.

        Raises:
            WebhookSignatureError: no signature was supplied, or it does not match.
        """
        if not isinstance(raw_body, bytes):
            raise TypeError(
                "the webhook body must be the raw bytes as received; a str would have to be "
                "encoded to be hashed, and the encoding chosen here is exactly the gap a "
                "forged request fits through"
            )
        if not signature:
            raise WebhookSignatureError("the request carried no gateway signature")

        expected = hmac.new(self._secret, raw_body, self._digest).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise WebhookSignatureError("the request signature did not match")


@dataclass(frozen=True)
class PaymentWebhookMessage:
    """What this context takes from a gateway's charge notification.

    Four fields out of the dozens a gateway sends. Nothing about the customer, the card, the
    channel or the fees: the party is read off the intent, and the rest is either not this
    context's business or is a fact it would then have to keep in step with the gateway's.
    """

    reference: str
    succeeded: bool
    amount: Decimal | None
    """In naira, converted from the minor unit. ``None`` for a failed attempt."""
    occurred_at: datetime

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "PaymentWebhookMessage | None":
        """Build a message from a *verified* payload, or ``None`` if it is not our business.

        Only ever called after :meth:`WebhookSignatureVerifier.verify` has returned. An
        unrecognised event gives ``None`` — see this module's docstring on why silence is the
        safe answer — while a recognised event in a shape this cannot read raises, because
        the gateway telling us about a charge in terms we do not understand is not something
        to shrug at.

        Raises:
            MalformedWebhookError: a success or failure event without a readable reference,
                amount or timestamp.
        """
        event = payload.get("event")
        if event not in SUCCESS_EVENTS and event not in FAILURE_EVENTS:
            return None

        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise MalformedWebhookError(f"{event} arrived with no data object")

        succeeded = event in SUCCESS_EVENTS
        return cls(
            reference=cls._reference(data),
            succeeded=succeeded,
            amount=cls._amount(data) if succeeded else None,
            occurred_at=cls._occurred_at(data),
        )

    @staticmethod
    def _reference(data: Mapping[str, object]) -> str:
        reference = data.get("reference")
        if not isinstance(reference, str) or not reference.strip():
            raise MalformedWebhookError("the charge carried no reference to reconcile against")
        return reference.strip()

    @staticmethod
    def _amount(data: Mapping[str, object]) -> Decimal:
        """Read the confirmed amount, in kobo, and convert it exactly.

        An ``int`` and nothing else. A JSON number with a decimal point parses as a ``float``,
        and a float has already lost the precision a ledger exists to keep —
        :class:`~billing.domain.values.Money` would refuse it downstream, and refusing it here
        names the reason. Dividing an ``int`` by 100 in ``Decimal`` is exact and lands on
        exactly the two decimal places kobo can express.
        """
        amount = data.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise MalformedWebhookError(
                f"the charge amount {amount!r} is not a whole number of kobo; an amount that "
                "cannot be read exactly must not be written to a ledger"
            )
        return Decimal(amount) / KOBO_PER_NAIRA

    @staticmethod
    def _occurred_at(data: Mapping[str, object]) -> datetime:
        """Read when the gateway says this happened, in ISO-8601.

        The gateway's instant rather than this system's, because it is the one that will still
        make sense when a payment recorded during an outage is reconciled days later. Any
        timezone it carries is kept: normalising it is the sort of helpfulness that turns into
        a ledger entry dated an hour out.
        """
        for field in ("paid_at", "paidAt", "created_at", "createdAt"):
            raw = data.get(field)
            if isinstance(raw, str) and raw.strip():
                try:
                    return datetime.fromisoformat(raw.strip())
                except ValueError as unreadable:
                    raise MalformedWebhookError(
                        f"the charge timestamp {raw!r} is not ISO-8601"
                    ) from unreadable
        raise MalformedWebhookError("the charge carried no timestamp; a ledger entry must be dated")


class PaymentWebhookHandler:
    """Verifies a gateway callback, then lets ``ConfirmPayment`` decide what it means."""

    def __init__(self, verifier: WebhookSignatureVerifier, confirm_payment: ConfirmPayment) -> None:
        self._verifier = verifier
        self._confirm_payment = confirm_payment

    @property
    def signature_header(self) -> str:
        """Which header the transport in front of this should hand over as ``signature``."""
        return self._verifier.header

    async def handle(self, raw_body: bytes, signature: str | None) -> PaymentConfirmed | None:
        """Verify, then act. In that order, and the order is the security property.

        Returns what the confirmation did, or ``None`` for an event this context has no
        opinion about. A replayed delivery returns a :class:`PaymentConfirmed` reporting
        ``was_replay``, having changed nothing: idempotency is the ledger's and the intent's,
        both keyed on the gateway reference, so this adapter needs no de-duplication of its
        own and deliberately has none.

        Args:
            raw_body: the request body exactly as received, before any parsing. A framework
                that has already decoded it to a dict has destroyed the thing being verified;
                the bytes are what was signed.
            signature: the value of :attr:`signature_header`, or ``None`` if absent.

        Raises:
            WebhookSignatureError: the request is not from the gateway. Nothing is read,
                nothing is parsed, and nothing is written.
            MalformedWebhookError: a signed charge notification this cannot read.
            PaymentIntentNotFoundError: a signed notification for a reference this university
                never issued.
        """
        self._verifier.verify(raw_body, signature)

        # Reached only by a request that carried this secret's signature over these bytes.
        message = PaymentWebhookMessage.from_payload(self._decode(raw_body))
        if message is None:
            return None

        return await self._confirm_payment.execute(
            ConfirmPaymentCommand(
                reference=message.reference,
                paid_at=message.occurred_at,
                succeeded=message.succeeded,
                amount=message.amount,
                failure_reason=(
                    None if message.succeeded else "the gateway reported the charge failed"
                ),
            )
        )

    @staticmethod
    def _decode(raw_body: bytes) -> Mapping[str, object]:
        try:
            payload = json.loads(raw_body)
        except ValueError as unreadable:
            raise MalformedWebhookError("the request body is not valid JSON") from unreadable
        if not isinstance(payload, Mapping):
            raise MalformedWebhookError("the request body is not a JSON object")
        return payload
