"""Wiring for the Billing tests.

This module is the swap point, and Phase 6.1 is what it was waiting for. The three
repositories now come from ``adapters``, which resolves to the in-memory classes or the
Postgres ones depending on ``UMS_TEST_BACKEND`` — see ``tests/conftest.py``. The publisher
still remembers rather than reaching a broker; that is a later swap and a different port.

Adapter construction still happens *only* here, and the repository fixtures are still
annotated with their port types rather than the concrete class. The schedule repository and
the publisher keep concrete annotations for the reason they always had — tests publish
schedules through the first and read ``published`` off the second — though only the publisher
is genuinely unswappable, since ``add`` is on the schedule port.

It is also this context's **composition root**. The ``wired_bus`` fixture is the one place
where Faculty & Department's publisher and Billing's handler are introduced to each other, and
it is deliberately a *test* module rather than production code: neither context may import the
other (CLAUDE.md section 4), so somebody outside both has to do the introducing. In Phase 6
that somebody is the application's startup; today it is this file, in the same way every other
context is wired by its own conftest.

**The fee amounts below are test fixtures, not institutional facts.** Real fees are set by the
university (CLAUDE.md section 6) and enter the system on a published ``FeeSchedule``; nothing
in ``src/`` contains an amount. They are round numbers here so that a reader can check the
arithmetic in their head, which is the whole reason a ledger test is worth reading.

The domain tests take nothing from this file. They build accounts and schedules directly,
because a domain test that needed a repository would be evidence that logic had leaked out of
the domain layer (CLAUDE.md section 2).
"""

from decimal import Decimal

import pytest
from tests.conftest import Adapters

from billing.adapters.inbound import (
    SESSION_OPENED,
    OfferAcceptedHandler,
    PaymentWebhookHandler,
    SessionOpenedHandler,
    WebhookSignatureVerifier,
)
from billing.adapters.outbound import (
    InMemoryEventPublisher,
    InMemoryFeeScheduleRepository,
    StubPaymentGateway,
)
from billing.application import (
    ApplySessionFees,
    ConfirmPayment,
    InitiatePayment,
    LinkStudentAccount,
    OpenAccountForOffer,
    ReadAccount,
    ReconcilePaymentIntents,
    RecordPayment,
)
from billing.domain import FeeSchedule, Level, Money, SessionFeeLine
from billing.ports import AccountRepositoryPort, PaymentIntentRepositoryPort
from faculty_department.adapters.outbound import InMemoryEventBus

SESSION_2026 = "sess-2026"
CSC_PROGRAM_ID = "prog-csc-bsc"
MCB_PROGRAM_ID = "prog-mcb-bsc"

ACCEPTANCE_FEE = Money(Decimal("20000"))
MATRICULATION_FEE = Money(Decimal("50000"))
CSC_SESSION_FEE = Money(Decimal("100000"))
MCB_SESSION_FEE = Money(Decimal("120000"))

WEBHOOK_SECRET = "sk_test_not_a_real_key"
"""A test fixture and nothing more.

The real secret is a rotated key that lives in the environment and reaches the verifier as a
constructor argument (``backend/.env.example`` names it ``PAYSTACK_SECRET_KEY``). That a test
can pick its own is the whole benefit of the secret being injected rather than read: nothing
in ``src/`` touches ``os.environ``, so nothing here has to pretend to be a deployment.
"""


def a_schedule(session_id: str = SESSION_2026, **overrides: object) -> FeeSchedule:
    """A published schedule pricing both programs at entry level."""
    fields: dict[str, object] = {
        "acceptance_fee": ACCEPTANCE_FEE,
        "matriculation_fee": MATRICULATION_FEE,
        "session_fees": (
            SessionFeeLine(program_id=CSC_PROGRAM_ID, level=Level(100), amount=CSC_SESSION_FEE),
            SessionFeeLine(program_id=MCB_PROGRAM_ID, level=Level(100), amount=MCB_SESSION_FEE),
        ),
    }
    fields.update(overrides)
    return FeeSchedule.for_session(session_id, **fields)  # type: ignore[arg-type]


@pytest.fixture
def accounts(adapters: Adapters) -> AccountRepositoryPort:
    return adapters.accounts()


@pytest.fixture
def schedules(adapters: Adapters) -> InMemoryFeeScheduleRepository:
    """Concrete on purpose: tests publish schedules through it.

    ``add`` *is* on the port, so this swaps with the backend like any other repository. The
    annotation names the in-memory class because that is what a reader looking for the
    publishing helper needs.
    """
    return adapters.schedules()


@pytest.fixture
def events() -> InMemoryEventPublisher:
    """Concrete on purpose: tests read ``published`` off it, which is not on the port."""
    return InMemoryEventPublisher()


@pytest.fixture
async def published_schedule(schedules: InMemoryFeeScheduleRepository) -> FeeSchedule:
    """The 2026 schedule, already published. What most tests assume exists."""
    schedule = a_schedule()
    await schedules.add(schedule)
    return schedule


@pytest.fixture
def open_account_for_offer(
    accounts: AccountRepositoryPort,
    schedules: InMemoryFeeScheduleRepository,
    events: InMemoryEventPublisher,
) -> OpenAccountForOffer:
    return OpenAccountForOffer(accounts, schedules, events)


@pytest.fixture
def apply_session_fees(
    accounts: AccountRepositoryPort,
    schedules: InMemoryFeeScheduleRepository,
    events: InMemoryEventPublisher,
) -> ApplySessionFees:
    return ApplySessionFees(accounts, schedules, events)


@pytest.fixture
def record_payment(
    accounts: AccountRepositoryPort, events: InMemoryEventPublisher
) -> RecordPayment:
    return RecordPayment(accounts, events)


@pytest.fixture
def intents(adapters: Adapters) -> PaymentIntentRepositoryPort:
    return adapters.intents()


@pytest.fixture
def gateway() -> StubPaymentGateway:
    """Concrete on purpose: tests script its answers and read ``asked`` off it."""
    return StubPaymentGateway()


@pytest.fixture
def initiate_payment(
    accounts: AccountRepositoryPort, intents: PaymentIntentRepositoryPort
) -> InitiatePayment:
    return InitiatePayment(accounts, intents)


@pytest.fixture
def confirm_payment(
    intents: PaymentIntentRepositoryPort, record_payment: RecordPayment
) -> ConfirmPayment:
    return ConfirmPayment(intents, record_payment)


@pytest.fixture
def reconcile_payment_intents(
    intents: PaymentIntentRepositoryPort,
    gateway: StubPaymentGateway,
    confirm_payment: ConfirmPayment,
) -> ReconcilePaymentIntents:
    return ReconcilePaymentIntents(intents, gateway, confirm_payment)


@pytest.fixture
def webhook_secret() -> str:
    """The shared secret, as a fixture so a test can sign with it without importing it."""
    return WEBHOOK_SECRET


@pytest.fixture
def verifier(webhook_secret: str) -> WebhookSignatureVerifier:
    return WebhookSignatureVerifier(webhook_secret)


@pytest.fixture
def payment_webhook(
    verifier: WebhookSignatureVerifier, confirm_payment: ConfirmPayment
) -> PaymentWebhookHandler:
    return PaymentWebhookHandler(verifier, confirm_payment)


@pytest.fixture
def link_student_account(accounts: AccountRepositoryPort) -> LinkStudentAccount:
    return LinkStudentAccount(accounts)


@pytest.fixture
def read_account(accounts: AccountRepositoryPort) -> ReadAccount:
    return ReadAccount(accounts)


@pytest.fixture
def offer_accepted_handler(open_account_for_offer: OpenAccountForOffer) -> OfferAcceptedHandler:
    return OfferAcceptedHandler(open_account_for_offer)


@pytest.fixture
def session_opened_handler(apply_session_fees: ApplySessionFees) -> SessionOpenedHandler:
    return SessionOpenedHandler(apply_session_fees)


@pytest.fixture
def wired_bus(session_opened_handler: SessionOpenedHandler) -> InMemoryEventBus:
    """A bus with Billing listening on it. The composition root, in two lines.

    Faculty & Department publishes into this; a batch of charges comes out the other side.
    Nothing in ``src/`` knows both halves, and that this fixture does is what makes it wiring.

    ``OfferAccepted`` is not subscribed here, because Admissions publishes nothing yet — see
    ``billing.adapters.inbound.offer_accepted_handler``. That handler is driven directly.
    """
    bus = InMemoryEventBus()
    bus.subscribe(SESSION_OPENED, session_opened_handler.on_message)
    return bus
