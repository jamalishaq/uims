"""Outbound port for turning an authenticated credential into tokens.

**Why this is a port and not a function call.** Signing a JWT is done by a third-party library
against a secret out of the environment, which makes it infrastructure by both of this
repository's tests for the word: it cannot run in a domain test, and it is the kind of thing a
deployment swaps. A use case that reached for ``jwt.encode`` directly would be an application
module holding a signing key.

It is also the seam that keeps ``security.py`` and this context apart. The adapter behind this
port is the one module in ``identity/`` that knows ``TokenCodec`` exists; everything above it
asks for tokens and is handed strings.

It is **not a query port into another context** — a signing key is infrastructure, not one of
the eight — so Identity still queries nobody. It is this context's counterpart to Billing's
``PaymentGatewayPort``, which makes the same argument about a payment gateway.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from identity.domain.credential import Credential


@dataclass(frozen=True)
class IssuedTokens:
    """What a successful login hands back.

    ``expires_in_seconds`` describes the *access* token only. The refresh token's lifetime is
    deliberately not reported: it lives in an ``HttpOnly`` cookie the client cannot read, and
    telling a client when a cookie it cannot see will expire would invite it to build a timer
    around a value it has no way to check.
    """

    access_token: str
    refresh_token: str
    expires_in_seconds: int
    token_type: str = "bearer"


class TokenIssuerPort(ABC):
    """Signs tokens for a credential that has already proved who it is.

    Every method here takes a whole :class:`Credential` rather than an id, because a token
    carries the role and the scope and reading them off the aggregate is what stops a caller
    assembling a token for a principal it did not authenticate.
    """

    @abstractmethod
    async def issue(self, credential: Credential) -> IssuedTokens:
        """Mint a fresh access/refresh pair.

        Raises:
            TokenIssuanceError: the tokens could not be signed.
        """

    @abstractmethod
    async def reissue_access(self, credential: Credential) -> IssuedTokens:
        """Mint a new access token against an unexpired session.

        Returns an :class:`IssuedTokens` whose ``refresh_token`` is empty: the refresh cookie is
        not rotated, because there is no server-side record against which a rotated one could be
        checked, and issuing a new one without that record would extend the session's life every
        time a page loaded — a 12-hour window that never closes. ``auth.md`` records the
        rotation decision as open rather than shipping the illusion of it.
        """

    @abstractmethod
    async def principal_of_refresh_token(self, refresh_token: str) -> str | None:
        """The login id a refresh token names, or ``None`` if it cannot be trusted.

        ``None`` rather than an exception, and the login id rather than a whole principal, for
        one reason each. Absence is normal — a cookie expires while a tab is open — and the
        caller's next act is a lookup, so what it needs from the token is a key. **The
        credential is then re-read from storage**, so a role changed or a credential deactivated
        since the token was signed takes effect on the next refresh rather than in twelve hours.
        """
