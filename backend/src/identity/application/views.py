"""Primitives-shaped projections of what this context's use cases return.

What leaves the building is a role as the string a token carries and a scope as its two parts.
No password hash appears in any view here, and none ever should: a view is what a route
serialises, and a hash that reached a view would be one careless ``response_model`` away from
the wire.
"""

from dataclasses import dataclass

from identity.domain.credential import Credential
from identity.ports.token_issuer import IssuedTokens


@dataclass(frozen=True)
class PrincipalView:
    """Who somebody is, as much as this context knows and no more.

    Deliberately without a name. CLAUDE.md section 6 gives the reason for the context and it
    applies just as hard to its read model: a client that wants a display name asks the context
    that owns the person — Student Profile for a student, Faculty & Department for a lecturer —
    with ``principal_id`` in hand. A ``full_name`` here would be the second copy, and the second
    copy is the one that goes stale.
    """

    principal_id: str
    login_id: str
    role: str
    scope_kind: str
    scope_id: str
    is_active: bool

    @classmethod
    def of(cls, credential: Credential) -> "PrincipalView":
        """Project a credential. The only place in this context that reads one field by field."""
        return cls(
            principal_id=credential.principal_id,
            login_id=credential.login_id,
            role=credential.role.value,
            scope_kind=credential.scope.kind.value,
            scope_id=credential.scope.unit_id,
            is_active=credential.is_active,
        )


@dataclass(frozen=True)
class SessionView:
    """A successful login: the tokens, and who they were issued to.

    The principal travels back with the tokens so a client can render a shell without decoding
    the JWT itself. A client *may* decode it — the claims are the same — but a client that has
    to is a client that has to keep a JWT library in step with this server's claim names.
    """

    access_token: str
    refresh_token: str
    token_type: str
    expires_in_seconds: int
    principal: PrincipalView

    @classmethod
    def of(cls, credential: Credential, tokens: IssuedTokens) -> "SessionView":
        return cls(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in_seconds=tokens.expires_in_seconds,
            principal=PrincipalView.of(credential),
        )
