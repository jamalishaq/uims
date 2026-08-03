"""A scriptable ``PaymentGatewayPort`` that talks to nobody.

Beside the real client rather than in the test tree, on the precedent Enrollment set with
``StubFinancialClearanceAdapter``: an adapter whose whole job is to stand in for an external
system is still an adapter, and keeping it here means the composition root of a test and the
composition root of a demo wire the same shape.

**It is not a mock and it records nothing about how it was called** — except which references
were asked about, which is the one thing worth asserting on: reconciliation's most important
property is what it does *not* do, and "an intent still inside its TTL was never verified"
needs the absence of a call to be observable.

The real client is Phase 6's, and it is where CLAUDE.md section 4's resilience rules land:
explicit timeouts, retries with exponential backoff and jitter on transient errors only, a
circuit breaker, and ``httpx``'s exceptions translated into
:class:`~billing.ports.payment_gateway.PaymentGatewayUnavailableError` before they can reach
the application layer. None of that is simulated here; what is simulated is the *answer*, and
the unreachable case is scripted directly because the use case's handling of it is a rule
worth a test of its own.
"""

from billing.domain.gateway import GatewayStatus, GatewayVerification
from billing.ports.payment_gateway import PaymentGatewayPort, PaymentGatewayUnavailableError


class StubPaymentGateway(PaymentGatewayPort):
    """Answers whatever it has been told to answer about each reference."""

    def __init__(self, *, default: GatewayStatus = GatewayStatus.UNKNOWN) -> None:
        self._answers: dict[str, GatewayVerification] = {}
        self._unreachable: set[str] = set()
        self._default = default
        self._asked: list[str] = []

    # ---- scripting ----

    def will_answer(self, verification: GatewayVerification) -> None:
        """Script the answer for one reference."""
        self._answers[verification.reference] = verification
        self._unreachable.discard(verification.reference)

    def will_be_unreachable_for(self, reference: str) -> None:
        """Script this reference to raise, as an exhausted retry chain would."""
        self._unreachable.add(reference)
        self._answers.pop(reference, None)

    @property
    def asked(self) -> tuple[str, ...]:
        """Every reference this gateway was asked about, in order, including repeats."""
        return tuple(self._asked)

    # ---- the port ----

    async def verify(self, reference: str) -> GatewayVerification:
        """Return the scripted answer, defaulting to "never heard of it".

        The default is :attr:`~billing.domain.gateway.GatewayStatus.UNKNOWN` because that is
        what a real gateway says about the majority of references a sweep will ever ask about:
        checkouts that were opened and walked away from.
        """
        self._asked.append(reference)
        if reference in self._unreachable:
            raise PaymentGatewayUnavailableError(
                f"the gateway could not be reached about {reference}"
            )
        return self._answers.get(
            reference, GatewayVerification(reference=reference, status=self._default)
        )
