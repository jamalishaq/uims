"""Use cases: logging in, refreshing, and the administrative half."""

from identity.application.authenticate import Authenticate, AuthenticateCommand
from identity.application.errors import (
    ApplicationError,
    AuthenticationFailedError,
    CredentialNotFoundError,
    LoginIdAlreadyIssuedError,
    PrincipalAlreadyHasCredentialError,
    UnknownRoleError,
)
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

__all__ = [
    "ApplicationError",
    "Authenticate",
    "AuthenticateCommand",
    "AuthenticationFailedError",
    "ChangePassword",
    "ChangePasswordCommand",
    "CredentialNotFoundError",
    "IssueCredential",
    "IssueCredentialCommand",
    "LoginIdAlreadyIssuedError",
    "PrincipalAlreadyHasCredentialError",
    "PrincipalView",
    "ReadPrincipal",
    "RefreshSession",
    "RefreshSessionCommand",
    "ResetPassword",
    "ResetPasswordCommand",
    "SessionView",
    "SetCredentialActive",
    "SetCredentialActiveCommand",
    "UnknownRoleError",
]
