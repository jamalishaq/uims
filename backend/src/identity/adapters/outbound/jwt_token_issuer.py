"""``TokenIssuerPort`` over ``security.TokenCodec``.

**The one module in this context that knows the codec exists.** Everything above it asks for
tokens and is handed strings, which is what lets the use cases be tested with a fake issuer and
no signing key anywhere near them.

It imports ``security``, a flat module, exactly as every context's Postgres adapter imports
``persistence`` and every router imports ``http_api``. That is not a cross-context import: rule
(b) of the fitness test only fires on the eight context packages, and ``security.py`` is
deliberately not one of them — see its docstring.

The translation this adapter performs is small and worth naming anyway, because it is the
anti-corruption layer working in the direction people forget. ``security`` speaks in
``Principal``; this context speaks in ``Credential``. Neither type crosses: the adapter reads
the aggregate's fields and builds the transport's value object, and nothing above it ever holds
a ``Principal``.
"""

import security
from identity.domain.credential import Credential
from identity.ports.errors import TokenIssuanceError
from identity.ports.token_issuer import IssuedTokens, TokenIssuerPort


class JwtTokenIssuer(TokenIssuerPort):
    """Signs the access/refresh pair a login is owed."""

    def __init__(self, codec: security.TokenCodec) -> None:
        self._codec = codec

    async def issue(self, credential: Credential) -> IssuedTokens:
        principal = self._principal_of(credential)
        try:
            return IssuedTokens(
                access_token=self._codec.issue_access(principal),
                refresh_token=self._codec.issue_refresh(principal),
                expires_in_seconds=self._codec.access_ttl_seconds,
            )
        except Exception as unsignable:
            raise TokenIssuanceError("the session tokens could not be signed") from unsignable

    async def reissue_access(self, credential: Credential) -> IssuedTokens:
        """A new access token, and no new refresh token.

        ``refresh_token`` comes back empty rather than repeated, so a caller that forwards this
        straight into a ``Set-Cookie`` writes nothing instead of silently re-stamping the old
        cookie with a fresh 12-hour window. The port's docstring gives the reasoning; this is
        the line that implements it.
        """
        try:
            return IssuedTokens(
                access_token=self._codec.issue_access(self._principal_of(credential)),
                refresh_token="",
                expires_in_seconds=self._codec.access_ttl_seconds,
            )
        except Exception as unsignable:
            raise TokenIssuanceError("the access token could not be signed") from unsignable

    async def principal_of_refresh_token(self, refresh_token: str) -> str | None:
        """The login id the cookie names, or ``None`` if it cannot be trusted.

        Catches only ``SecurityError``. A broad ``except`` here would turn a misconfigured
        signing key into "your session expired", and the deployment would never find out
        (CLAUDE.md section 4 on not papering over failures).
        """
        try:
            principal = self._codec.decode(refresh_token, expected_type=security.REFRESH_TOKEN)
        except security.SecurityError:
            return None
        return principal.login_id

    @staticmethod
    def _principal_of(credential: Credential) -> security.Principal:
        """``Credential`` to ``Principal``: the only place the two vocabularies meet.

        The enum values are the wire format on both sides and
        ``tests/identity/test_role_vocabulary_agrees.py`` asserts they stay identical, so this
        is a lookup by value rather than a mapping table somebody has to maintain.
        """
        return security.Principal(
            subject=credential.principal_id,
            login_id=credential.login_id,
            role=security.Role(credential.role.value),
            scope_kind=security.ScopeKind(credential.scope.kind.value),
            scope_id=credential.scope.unit_id,
        )
