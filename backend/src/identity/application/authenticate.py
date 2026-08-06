"""Logging in: the one use case the whole context exists for."""

from dataclasses import dataclass

from identity.application.errors import AuthenticationFailedError
from identity.domain.errors import CredentialInactiveError
from identity.ports.credential_repository import CredentialRepositoryPort
from identity.ports.token_issuer import TokenIssuerPort


@dataclass(frozen=True)
class AuthenticateCommand:
    """A login id and a password, exactly as typed.

    The password is not normalised in any way — not stripped, not case-folded. Whatever the
    person typed is what was hashed when the credential was created, and the only way the two
    agree is if neither end touches it.
    """

    login_id: str
    password: str


class Authenticate:
    """Check a password and, if it is right, issue a session.

    Reads the credential, asks the *aggregate* whether the password is correct, and hands the
    aggregate to the issuer. The password never leaves this method and the hash never enters it.
    """

    def __init__(self, credentials: CredentialRepositoryPort, tokens: TokenIssuerPort) -> None:
        self._credentials = credentials
        self._tokens = tokens

    async def execute(self, command: AuthenticateCommand):
        """Return ``(credential, tokens)``, or raise :class:`AuthenticationFailedError`.

        Every way this fails raises the same exception with the same message — see that class
        on why an unknown login id and a wrong password must not be distinguishable.

        **The successful path may write.** A credential whose hash was made under weaker scrypt
        parameters is re-hashed here and saved, because a correct login is the only moment the
        plaintext is legitimately in hand. A save that fails would raise rather than log, which
        is deliberate: the alternative is a login that appears to succeed while the upgrade
        silently never happens, forever.
        """
        credential = await self._credentials.find_by_login_id(command.login_id)
        if credential is None:
            raise AuthenticationFailedError("login id or password is incorrect")
        try:
            if not credential.authenticate(command.password):
                raise AuthenticationFailedError("login id or password is incorrect")
        except CredentialInactiveError as inactive:
            raise AuthenticationFailedError("login id or password is incorrect") from inactive

        if credential.password_hash.needs_rehash:
            credential.rehash(command.password)
            await self._credentials.save(credential)

        return credential, await self._tokens.issue(credential)
