"""Exchanging a refresh token for a new access token."""

from dataclasses import dataclass

from identity.application.errors import AuthenticationFailedError
from identity.ports.credential_repository import CredentialRepositoryPort
from identity.ports.token_issuer import TokenIssuerPort


@dataclass(frozen=True)
class RefreshSessionCommand:
    """The refresh token, as it came out of the cookie."""

    refresh_token: str


class RefreshSession:
    """Mint a new access token for a session that is still alive.

    **The credential is re-read from storage rather than trusted out of the token**, which is
    the whole reason this is a use case and not a re-signing function. A refresh token is valid
    for twelve hours and carries the role and scope frozen at login; a registrar who was moved
    to another department, or a credential that has since been deactivated, would otherwise keep
    the authority the token remembers until it expired. Re-reading makes the blast radius of any
    of those changes one access-token lifetime — thirty minutes — instead of twelve hours.

    That is also the closest thing to revocation this system has, and it is not a substitute for
    it: deactivating a credential stops the *next* refresh, not the access token already in a
    browser tab. ``auth.md`` records real revocation as an open decision.
    """

    def __init__(self, credentials: CredentialRepositoryPort, tokens: TokenIssuerPort) -> None:
        self._credentials = credentials
        self._tokens = tokens

    async def execute(self, command: RefreshSessionCommand):
        """Return ``(credential, tokens)``, or raise :class:`AuthenticationFailedError`.

        One exception for all four failures — no token, an untrustworthy one, a login id that no
        longer exists, and a credential since deactivated — for the reason that class gives. A
        refresh endpoint that distinguished them would be the same enumeration oracle as a login
        endpoint that did, reachable without a password.
        """
        if not command.refresh_token:
            raise AuthenticationFailedError("the session could not be refreshed")
        login_id = await self._tokens.principal_of_refresh_token(command.refresh_token)
        if login_id is None:
            raise AuthenticationFailedError("the session could not be refreshed")

        credential = await self._credentials.find_by_login_id(login_id)
        if credential is None or not credential.is_active:
            raise AuthenticationFailedError("the session could not be refreshed")

        return credential, await self._tokens.reissue_access(credential)
