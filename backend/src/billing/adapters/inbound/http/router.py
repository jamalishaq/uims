"""HTTP routes for Billing: the ledger, checkouts, the gateway webhook and two admin sweeps.

**The webhook route is the security-sensitive one, and it is deliberately thin.**
``PaymentWebhookHandler`` already does the whole job — verify the signature over the raw bytes,
then parse, then act, in that order — and CLAUDE.md section 4 forbids refactoring that path
without human review. So this route adds nothing to it. It reads the body as ``bytes``, reads
the header the handler names, and hands both over. In particular:

* it does **not** declare a Pydantic body model, because a framework that has already parsed
  the body into a dict has destroyed the artifact the HMAC covers;
* it does **not** name the header itself, taking it from ``handler.signature_header``;
* it does **not** catch anything. ``WebhookSignatureError`` becomes a 401 with no detail
  through the context's error table, which is where that decision belongs and where it can be
  read in one place.

**No authentication exists in this phase.** Three routes here write money or move it —
``POST /payments``, ``POST /session-fees``, ``POST /reconciliations`` — and nothing in front of
them checks who is calling. They are here because Phase 6.2 exposes the use cases that exist,
and they must not be reachable from an untrusted network until an auth phase lands.
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

import security
from billing.adapters.inbound.http.schemas import (
    AccountStatementResponse,
    ApplySessionFeesRequest,
    InitiatePaymentRequest,
    LinkStudentAccountRequest,
    PaymentConfirmedResponse,
    PaymentInitiatedResponse,
    PaymentRecordedResponse,
    ReconcileRequest,
    ReconciliationSweptResponse,
    RecordPaymentRequest,
    SessionFeesAppliedResponse,
    StudentAccountLinkedResponse,
    WebhookAcceptedResponse,
)
from billing.adapters.inbound.payment_webhook import PaymentWebhookHandler
from billing.application.apply_session_fees import ApplySessionFees
from billing.application.initiate_payment import InitiatePayment, InitiatePaymentCommand
from billing.application.link_student_account import (
    LinkStudentAccount,
    LinkStudentAccountCommand,
)
from billing.application.read_account import ReadAccount
from billing.application.reconcile_payment_intents import ReconcilePaymentIntents
from billing.application.record_payment import RecordPayment, RecordPaymentCommand
from billing.application.views import (
    AccountStatementView,
    PaymentConfirmedView,
    PaymentInitiatedView,
    PaymentRecordedView,
)
from http_api import dependencies_of, error_responses

STATE_KEY = "billing"
"""Where this context's use cases hang on ``app.state``. Owned here, read by the root."""


class BillingDependencies:
    """The use cases this router needs, wired once at startup."""

    def __init__(
        self,
        read_account: ReadAccount,
        link_student_account: LinkStudentAccount,
        record_payment: RecordPayment,
        initiate_payment: InitiatePayment,
        apply_session_fees: ApplySessionFees,
        reconcile_payment_intents: ReconcilePaymentIntents,
        payment_webhook: PaymentWebhookHandler,
    ) -> None:
        self.read_account = read_account
        self.link_student_account = link_student_account
        self.record_payment = record_payment
        self.initiate_payment = initiate_payment
        self.apply_session_fees = apply_session_fees
        self.reconcile_payment_intents = reconcile_payment_intents
        self.payment_webhook = payment_webhook


def _deps(request: Request) -> BillingDependencies:
    return dependencies_of(request, STATE_KEY, BillingDependencies)


Deps = Annotated[BillingDependencies, Depends(_deps)]

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get(
    "/accounts/{party_id}",
    response_model=AccountStatementResponse,
    summary="Read a party's ledger",
    responses=error_responses(401, 403, 404, 422, 500, 503),
)
async def read_account(
    party_id: str, principal: security.Authenticated, deps: Deps
) -> AccountStatementResponse:
    """The whole ledger. ``party_id`` is an applicant id or a matric number — either resolves.

    A student reads their own ledger; the bursary reads anybody's. ``require_owner`` matches
    the token's subject *and* its login id, which is what lets a student quote the matric number
    printed on their ID card rather than the ``student_id`` only this system uses.

    **One case is refused that arguably should not be**, and it follows from the sentence above:
    an account still keyed by an *applicant id* — one opened at ``OfferAccepted`` and not yet
    linked at matriculation — is unreachable by the person it belongs to, because a token has
    never heard of an applicant id. It is reachable by the bursary, and it stops being a problem
    the moment ``LinkStudentAccount`` runs. Fixing it properly needs the applicant identity
    ``auth.md`` records as open.
    """
    principal.require_owner(party_id)
    statement = await deps.read_account.execute(party_id)
    return AccountStatementResponse.of(AccountStatementView.of(statement))


@router.post(
    "/accounts/{party_id}/student-link",
    response_model=StudentAccountLinkedResponse,
    summary="Link a matric number to an existing account",
    responses=error_responses(401, 403, 404, 409, 422, 500, 503),
)
async def link_student_account(
    party_id: str,
    body: LinkStudentAccountRequest,
    principal: security.University,
    deps: Deps,
) -> StudentAccountLinkedResponse:
    """Give the ledger opened at acceptance the matric number it now also answers to.

    There is no inbound event handler for this: no event in the system carries a matric number,
    and a handler for an event nobody publishes is wiring that can be neither right nor wrong.
    This route is how it happens.
    """
    linked = await deps.link_student_account.execute(
        LinkStudentAccountCommand(party_id=party_id, student_id=body.student_id)
    )
    return StudentAccountLinkedResponse(
        party_id=linked.party_id,
        student_id=linked.student_id,
        was_already_linked=linked.was_already_linked,
    )


@router.post(
    "/accounts/{party_id}/payments",
    status_code=status.HTTP_201_CREATED,
    response_model=PaymentRecordedResponse,
    summary="Record a payment against a ledger (bursary override)",
    responses=error_responses(401, 403, 404, 422, 500, 503),
)
async def record_payment(
    party_id: str,
    body: RecordPaymentRequest,
    principal: security.University,
    deps: Deps,
) -> PaymentRecordedResponse:
    """Write down money that arrived by some route other than the gateway.

    **Unauthenticated in this phase.** A gateway's payment carries a signature proving who sent
    it; this one carries nothing. Do not expose this route publicly.

    A repeated ``gateway_ref`` is a no-op rather than an error — idempotency is the ledger's
    invariant — and the response says which happened in ``was_duplicate``.
    """
    recorded = await deps.record_payment.execute(
        RecordPaymentCommand(
            party_id=party_id,
            gateway_ref=body.gateway_ref,
            amount=body.amount,
            received_at=body.received_at,
        )
    )
    return PaymentRecordedResponse.of(PaymentRecordedView.of(recorded))


@router.post(
    "/payment-intents",
    status_code=status.HTTP_201_CREATED,
    response_model=PaymentInitiatedResponse,
    summary="Open a checkout",
    responses=error_responses(401, 403, 404, 409, 422, 500, 503),
)
async def initiate_payment(
    body: InitiatePaymentRequest, principal: security.Authenticated, deps: Deps
) -> PaymentInitiatedResponse:
    """Open an intent against a party's ledger, to be confirmed by the gateway's webhook.

    Checked against the ``party_id`` in the body, so nobody opens an intent against somebody
    else's ledger. That matters less than it looks — the party credited on confirmation is read
    off the *intent* and never off the webhook payload, so a mis-aimed intent cannot move money
    to the wrong account — but an unauthenticated caller could otherwise fill another student's
    ledger with intents and the reconciliation sweep with noise.
    """
    principal.require_owner(body.party_id)
    initiated = await deps.initiate_payment.execute(
        InitiatePaymentCommand(
            party_id=body.party_id,
            reference=body.reference,
            amount=body.amount,
            initiated_at=body.initiated_at,
            ttl=None if body.ttl_seconds is None else timedelta(seconds=body.ttl_seconds),
        )
    )
    return PaymentInitiatedResponse.of(PaymentInitiatedView.of(initiated))


@router.post(
    "/webhooks/paystack",
    response_model=WebhookAcceptedResponse,
    summary="Gateway payment callback",
    responses=error_responses(400, 401, 404, 409, 422, 500, 503),
)
async def paystack_webhook(request: Request, deps: Deps) -> WebhookAcceptedResponse:
    """Verify the gateway's signature over the raw body, then let ``ConfirmPayment`` decide.

    The body is read as bytes and passed through untouched. Any normalisation before hashing
    is a bypass: the attacker signs one document and the system acts on a different one.

    An event this context has no opinion about returns ``handled: false`` and a 200. Silence is
    safe here *because* reconciliation exists — anything a webhook fails to deliver is caught by
    the sweep asking the gateway directly.
    """
    handler = deps.payment_webhook
    raw_body = await request.body()
    signature = request.headers.get(handler.signature_header)

    confirmed = await handler.handle(raw_body, signature)
    if confirmed is None:
        return WebhookAcceptedResponse(handled=False)
    return WebhookAcceptedResponse(
        handled=True, result=PaymentConfirmedResponse.of(PaymentConfirmedView.of(confirmed))
    )


@router.post(
    "/session-fees",
    response_model=SessionFeesAppliedResponse,
    summary="Apply a session's fee schedule to every active account",
    responses=error_responses(401, 403, 404, 422, 500, 503),
)
async def apply_session_fees(
    body: ApplySessionFeesRequest, principal: security.University, deps: Deps
) -> SessionFeesAppliedResponse:
    """Run the batch by hand.

    Normally driven by ``SessionOpened``; this route exists because a bursar who publishes a
    schedule after the session opened needs a way to run it again. It is safe to repeat: a
    charge is raised once per ``(kind, session_id)``, so a second run charges nobody twice.
    """
    applied = await deps.apply_session_fees.execute(body.session_id)
    return SessionFeesAppliedResponse(
        session_id=applied.session_id,
        charged=applied.charged,
        already_charged=applied.already_charged,
        unpriced=applied.unpriced,
        considered=applied.considered,
    )


@router.post(
    "/reconciliations",
    response_model=ReconciliationSweptResponse,
    summary="Sweep open payment intents against the gateway",
    responses=error_responses(401, 403, 404, 409, 422, 500, 502, 503),
)
async def reconcile_payment_intents(
    body: ReconcileRequest, principal: security.University, deps: Deps
) -> ReconciliationSweptResponse:
    """Verify every expired intent with the gateway before writing any of them off.

    "Webhook lost but money taken" is the stuck state this exists to catch. An intent the
    gateway cannot be reached about is reported in ``unreachable`` and left open rather than
    abandoned.
    """
    swept = await deps.reconcile_payment_intents.execute(body.now)
    return ReconciliationSweptResponse(
        examined=swept.examined,
        skipped=swept.skipped,
        confirmed=swept.confirmed,
        failed=swept.failed,
        abandoned=swept.abandoned,
        pending=swept.pending,
        unreachable=swept.unreachable,
        recovered_money=swept.recovered_money,
    )


__all__ = ["STATE_KEY", "BillingDependencies", "router"]
