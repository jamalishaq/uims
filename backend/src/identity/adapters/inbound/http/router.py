"""HTTP routes for Identity: the doors, and the administration of who has keys.

Two of these routes are the only ones in the system reachable without a token, which is not a
gap but the definition of a login endpoint. Everything else here is guarded, and one route is
guarded in a way worth reading twice — see :func:`change_own_password`.

**The refresh token never appears in a response body.** It is set as an ``HttpOnly`` cookie and
read back off the request's cookies, so a script that gets onto the page cannot read it. Putting
it in the body "for convenience" would hand it to exactly the code the flag exists to exclude,
and it is the reason ``SessionResponse`` has no field for it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

import security
from http_api import dependencies_of, error_responses
from identity.adapters.inbound.http.schemas import (
    ChangePasswordRequest,
    IssueCredentialRequest,
    LoginRequest,
    PrincipalResponse,
    ResetPasswordRequest,
    SessionResponse,
    SetCredentialActiveRequest,
)
from identity.application.authenticate import Authenticate, AuthenticateCommand
from identity.application.errors import CredentialNotFoundError
from identity.application.provision_credentials import (
    ChangePassword,
    ChangePasswordCommand,
    IssueCredential,
    IssueCredentialCommand,
    ReadPrincipal,
    ResetPassword,
    ResetPasswordCommand,
    SetCredentialActive,
    SetCredentialActiveCommand,
)
from identity.application.refresh_session import RefreshSession, RefreshSessionCommand
from identity.application.views import PrincipalView, SessionView

STATE_KEY = "identity"
"""Where this context's use cases hang on ``app.state``. Owned here, read by the root."""

REFRESH_COOKIE = "ums_refresh"
"""The cookie the refresh token lives in.

Named rather than defaulted so that the route that sets it and the route that clears it cannot
disagree — a logout that cleared a differently-spelled cookie would leave the session alive and
look like it had ended.
"""


class IdentityDependencies:
    """The use cases this router needs, wired once at startup."""

    def __init__(
        self,
        authenticate: Authenticate,
        refresh_session: RefreshSession,
        issue_credential: IssueCredential,
        change_password: ChangePassword,
        reset_password: ResetPassword,
        set_credential_active: SetCredentialActive,
        read_principal: ReadPrincipal,
        refresh_cookie_max_age: int,
        cookies_require_https: bool,
    ) -> None:
        self.authenticate = authenticate
        self.refresh_session = refresh_session
        self.issue_credential = issue_credential
        self.change_password = change_password
        self.reset_password = reset_password
        self.set_credential_active = set_credential_active
        self.read_principal = read_principal
        self.refresh_cookie_max_age = refresh_cookie_max_age
        self.cookies_require_https = cookies_require_https
        """Whether the refresh cookie carries ``Secure``.

        A construction argument rather than a constant, because a developer on
        ``http://localhost`` cannot receive a ``Secure`` cookie at all and would be unable to log
        in. It defaults to *on* in the composition root and is switched off only where
        ``ALLOWED_ORIGINS`` says the frontend is on plain HTTP — so the insecure case is
        something a deployment has to have asked for.
        """


def _deps(request: Request) -> IdentityDependencies:
    return dependencies_of(request, STATE_KEY, IdentityDependencies)


Deps = Annotated[IdentityDependencies, Depends(_deps)]

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, token: str, deps: IdentityDependencies) -> None:
    """Write the refresh cookie, or write nothing if there is no token to write.

    The empty-token case is not defensive padding: ``reissue_access`` deliberately returns an
    empty refresh token because the cookie is *not* rotated, and this is the line that makes
    "not rotated" mean "untouched" rather than "re-stamped with a fresh twelve hours".
    """
    if not token:
        return
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=deps.refresh_cookie_max_age,
        httponly=True,
        secure=deps.cookies_require_https,
        samesite="lax",
        path="/",
    )


@router.post(
    "/login",
    response_model=SessionResponse,
    summary="Exchange a login id and password for a session",
    responses=error_responses(401, 422, 500, 503),
)
async def login(body: LoginRequest, response: Response, deps: Deps) -> SessionResponse:
    """The one route in this system that turns a password into authority.

    Every failure is a 401 with one message. An unknown login id, a wrong password and a
    deactivated credential are three different facts and deliberately one answer: login ids here
    are matric numbers and department codes, which are guessable in bulk, and an endpoint that
    distinguished them would let somebody enumerate the university's roll.
    """
    credential, tokens = await deps.authenticate.execute(
        AuthenticateCommand(login_id=body.login_id, password=body.password)
    )
    _set_refresh_cookie(response, tokens.refresh_token, deps)
    return SessionResponse.of(SessionView.of(credential, tokens))


@router.post(
    "/refresh",
    response_model=SessionResponse,
    summary="Exchange the refresh cookie for a new access token",
    responses=error_responses(401, 422, 500, 503),
)
async def refresh(request: Request, response: Response, deps: Deps) -> SessionResponse:
    """A new access token, from the cookie the browser holds and JavaScript cannot read.

    **The credential is re-read from storage**, not trusted out of the token: a role changed or
    a credential deactivated since login takes effect here rather than in twelve hours. The
    cookie itself is not rotated — see ``TokenIssuerPort.reissue_access`` on why extending the
    session's life on every page load would make a 12-hour window one that never closes.
    """
    credential, tokens = await deps.refresh_session.execute(
        RefreshSessionCommand(refresh_token=request.cookies.get(REFRESH_COOKIE, ""))
    )
    _set_refresh_cookie(response, tokens.refresh_token, deps)
    return SessionResponse.of(SessionView.of(credential, tokens))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear the refresh cookie",
)
async def logout(response: Response) -> None:
    """End the session on this browser.

    **It does not revoke anything**, and saying so plainly is better than implying otherwise:
    there is no server-side record of a refresh token, so a copy somebody else took keeps
    working until it expires, and an access token already issued keeps working for up to thirty
    minutes. ``auth.md`` records revocation as an open decision rather than pretending this
    route is one.

    Deliberately unauthenticated. A logout that required a valid token would refuse exactly the
    caller who most needs it — one whose access token has already expired — and leave the cookie
    in place.
    """
    response.delete_cookie(key=REFRESH_COOKIE, path="/")


@router.get(
    "/me",
    response_model=PrincipalResponse,
    summary="Who the bearer token says you are",
    responses=error_responses(401, 404, 500, 503),
)
async def read_me(principal: security.Authenticated, deps: Deps) -> PrincipalResponse:
    """Read back from storage rather than echoing the token.

    Echoing would be cheaper and would answer for a credential deleted an hour ago. This is the
    route a client calls on page load to decide what to render, and rendering an administrator's
    console for a credential that no longer exists is worse than a round trip.
    """
    credential = await deps.read_principal.find_by_login_id(principal.login_id)
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="the token names a credential that is no longer held",
        )
    return PrincipalResponse.of(PrincipalView.of(credential))


@router.post(
    "/me/password",
    response_model=PrincipalResponse,
    summary="Change your own password",
    responses=error_responses(401, 404, 422, 500, 503),
)
async def change_own_password(
    body: ChangePasswordRequest, principal: security.Authenticated, deps: Deps
) -> PrincipalResponse:
    """**The login id comes from the token, never from the body.**

    That is the whole security property of this route and the reason it takes no ``login_id``
    field. A body that named whose password to change would be an administrative reset wearing
    a self-service form: anybody with any valid token could re-password anybody else by knowing
    their login id, and the ``current_password`` check would be the only thing standing in the
    way — which is exactly the thing an attacker who is guessing is already trying to defeat.
    """
    credential = await deps.change_password.execute(
        ChangePasswordCommand(
            login_id=principal.login_id,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    )
    return PrincipalResponse.of(PrincipalView.of(credential))


@router.post(
    "/credentials",
    status_code=status.HTTP_201_CREATED,
    response_model=PrincipalResponse,
    summary="Issue a credential",
    responses=error_responses(401, 403, 409, 422, 500, 503),
)
async def issue_credential(
    body: IssueCredentialRequest,
    principal: security.University,
    deps: Deps,
) -> PrincipalResponse:
    """University-scoped, and no scope check beyond that.

    Creating logins is the one act that cannot be delegated downwards in this design: a faculty
    officer who could issue credentials could issue themselves a university-scoped one, and the
    role gate would then be decorative. Whether a real registry wants to delegate it — and what
    it would be bounded by — is not something this change may decide.
    """
    credential = await deps.issue_credential.execute(IssueCredentialCommand(**body.model_dump()))
    return PrincipalResponse.of(PrincipalView.of(credential))


@router.get(
    "/credentials",
    response_model=list[PrincipalResponse],
    summary="Every credential held",
    responses=error_responses(401, 403, 500, 503),
)
async def list_credentials(principal: security.University, deps: Deps) -> list[PrincipalResponse]:
    """The administrative roll. No hashes cross — ``PrincipalView`` has no field for one."""
    return [
        PrincipalResponse.of(PrincipalView.of(credential))
        for credential in await deps.read_principal.all()
    ]


@router.post(
    "/credentials/{login_id}/password",
    response_model=PrincipalResponse,
    summary="Reset somebody's password",
    responses=error_responses(401, 403, 404, 422, 500, 503),
)
async def reset_password(
    login_id: str,
    body: ResetPasswordRequest,
    principal: security.University,
    deps: Deps,
) -> PrincipalResponse:
    """Set a password without the old one. Separate from the self-service route on purpose.

    Two routes rather than one method with an optional ``current_password``, because an optional
    field is a guard somebody can switch off by omitting it.
    """
    credential = await deps.reset_password.execute(
        ResetPasswordCommand(login_id=login_id, new_password=body.new_password)
    )
    return PrincipalResponse.of(PrincipalView.of(credential))


@router.put(
    "/credentials/{login_id}/active",
    response_model=PrincipalResponse,
    summary="Enable or disable a login",
    responses=error_responses(401, 403, 404, 422, 500, 503),
)
async def set_credential_active(
    login_id: str,
    body: SetCredentialActiveRequest,
    principal: security.University,
    deps: Deps,
) -> PrincipalResponse:
    """Turn a login off without deleting what it was.

    ``PUT`` because it sets a state rather than appending an event, and idempotent in both
    directions: disabling a disabled login is a no-op, which is what a retry needs.
    """
    credential = await deps.set_credential_active.execute(
        SetCredentialActiveCommand(login_id=login_id, is_active=body.is_active)
    )
    return PrincipalResponse.of(PrincipalView.of(credential))


@router.get(
    "/credentials/{login_id}",
    response_model=PrincipalResponse,
    summary="Read one credential",
    responses=error_responses(401, 403, 404, 500, 503),
)
async def read_credential(
    login_id: str, principal: security.University, deps: Deps
) -> PrincipalResponse:
    """A 404 here is safe where the same answer at ``/login`` would not be.

    Reaching this route already required a university-scoped token, so telling the caller
    whether a login id exists gives away nothing they could not learn from the list above.
    """
    credential = await deps.read_principal.find_by_login_id(login_id)
    if credential is None:
        raise CredentialNotFoundError(f"no credential with login id {login_id!r}")
    return PrincipalResponse.of(PrincipalView.of(credential))


__all__ = ["REFRESH_COOKIE", "STATE_KEY", "IdentityDependencies", "router"]
