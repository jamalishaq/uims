"""Outbound port for asking a payment gateway what became of a reference.

**This is not a query port into another context, and the distinction is load-bearing.** Every
other port in this system either persists an aggregate or reaches one of the seven bounded
contexts, and CLAUDE.md section 3 is emphatic that the second kind is typed in the consuming
context's language with anti-corruption translation in the adapter. A payment gateway is
neither: it is a third party, outside this system entirely, run by a company that has never
heard of a matriculation fee. Billing still queries nobody — the property
``tests/billing/test_port_types_are_billing_owned.py`` exists to protect — and this port is
that test's one named exemption rather than a hole in it.

**One method, and it exists for one failure mode.** CLAUDE.md section 3: "before abandoning,
verify via ``PaymentGatewayPort.verify(reference)`` — 'webhook lost but money taken' is the
stuck state this exists to catch." A payer whose card was charged and whose callback was
dropped is otherwise indistinguishable from a payer who wandered off, and the difference is a
student who cannot register against a debt they have already settled. So the only thing this
port does is ask, about one reference, and the answer comes back as a
:class:`~billing.domain.gateway.GatewayVerification` — Billing's own reading, not the
gateway's JSON.

There is deliberately **no** ``charge``, ``initialize`` or ``refund`` here. Starting a
checkout is the frontend's business and the reference comes back to this system through
``InitiatePayment``; refunds are a deferred admin use case (CLAUDE.md section 3). A port that
could move money would make this context's blast radius the whole bursary rather than one
read.

The client behind this port is where CLAUDE.md section 4's resilience rules land: explicit
timeouts, retries with exponential backoff and jitter on transient errors only, and a circuit
breaker, since this is the external gateway call that rule names. None of that is visible
here, and it must not be — what a caller sees is an answer or one of the two errors below.
"""

from abc import ABC, abstractmethod

from billing.domain.gateway import GatewayVerification


class PaymentGatewayError(Exception):
    """Base class for every failure this port can raise.

    Declared beside the port rather than in :mod:`billing.ports.errors`, whose docstring
    scopes it to what a *repository* can raise. The two vocabularies are translated into by
    different adapters and neither is a kind of the other.
    """


class PaymentGatewayUnavailableError(PaymentGatewayError):
    """The gateway could not be reached, or gave up before answering.

    The type a client translates a timeout, a connection reset, a 5xx or an open circuit
    breaker into once its retries are exhausted — CLAUDE.md section 4: "raw driver/library
    exceptions (``psycopg``, ``httpx``) must never cross into the application layer".

    Distinctly **not** an answer about the payment. Reconciliation treats it as "ask again
    later" and leaves the intent open, because an unreachable gateway is evidence about the
    network and none at all about whether somebody's card was charged.
    """


class PaymentGatewayPort(ABC):
    """Asks the gateway what it knows about one payment reference."""

    @abstractmethod
    def verify(self, reference: str) -> GatewayVerification:
        """Return what the gateway reports about ``reference``.

        A reference the gateway does not recognise is a normal answer —
        :attr:`~billing.domain.gateway.GatewayStatus.UNKNOWN` — and not an error: it is the
        expected reply for an intent whose payer opened a checkout and never went through
        with it, which is most of the intents a sweep will ever look at.

        Raises:
            PaymentGatewayUnavailableError: the gateway could not be asked. The question is
                unanswered, which is not the same as answered "no".
        """
