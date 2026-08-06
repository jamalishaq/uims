"""Pydantic request and response models. They go no further than this package.

**No response model here has a ``password_hash`` field, and none ever should.** That is not an
oversight worth trusting to review: ``PrincipalView`` does not carry one either, so there is
nothing for a careless ``response_model`` to leak. This note is here because the absence is
load-bearing and reads like a gap.

**No ``min_length`` on any new password either**, and that absence is also deliberate. The
floor is ``MINIMUM_PASSWORD_LENGTH`` in ``domain/values.py``, where ``PasswordHash.of`` enforces
it, and rule (d) of the fitness test forbids this package from naming a domain module. Stating
the number here as a literal would put the policy in two places, and re-exporting it through
``application/`` to dodge the rule would be the same import wearing a hat (CLAUDE.md section 3
makes that argument about ``domain/errors.py``). So a short password is refused by the domain
and surfaces as a 422 through ``InvalidPasswordError`` — one rule, in the layer that owns it,
with a message that says what the floor is.
"""

from pydantic import BaseModel, ConfigDict, Field

from identity.application.views import PrincipalView, SessionView


class LoginRequest(BaseModel):
    """A login id and a password, as typed.

    ``password`` carries **no ``min_length``**, deliberately. A login form that refused a short
    password before checking it would tell an attacker that no account has one, and would tell
    a real person with a legacy password that their password is invalid rather than wrong. The
    floor applies where a password is *set*, not where one is offered.
    """

    model_config = ConfigDict(extra="forbid")

    login_id: str = Field(min_length=1, description="A matric number, a staff id, or a unit id.")
    password: str = Field(min_length=1)


class PrincipalResponse(BaseModel):
    """Who somebody is, as much as Identity knows.

    No name and no email — a client that wants a display name asks the context that owns the
    person, with ``principal_id`` in hand.
    """

    principal_id: str
    login_id: str
    role: str
    scope_kind: str
    scope_id: str
    is_active: bool

    @classmethod
    def of(cls, view: PrincipalView) -> "PrincipalResponse":
        return cls(**vars(view))


class SessionResponse(BaseModel):
    """What a successful login returns.

    **The refresh token is not a field here.** It leaves in an ``HttpOnly`` cookie the browser
    stores and JavaScript cannot read, which is the whole of its protection against a script
    that gets onto the page. Putting it in the body as well would hand it to exactly the code
    the cookie flag exists to keep it away from.
    """

    access_token: str
    token_type: str
    expires_in_seconds: int
    principal: PrincipalResponse

    @classmethod
    def of(cls, view: SessionView) -> "SessionResponse":
        return cls(
            access_token=view.access_token,
            token_type=view.token_type,
            expires_in_seconds=view.expires_in_seconds,
            principal=PrincipalResponse.of(view.principal),
        )


class IssueCredentialRequest(BaseModel):
    """A credential to create. University-scoped.

    ``scope_unit_id`` is optional and defaults to ``principal_id``, because for every role the
    seeder issues today the two are the same value. Supplying it is how a named office-holder
    would be expressed — a person whose principal is themselves and whose scope is the
    department they run.
    """

    model_config = ConfigDict(extra="forbid")

    login_id: str = Field(min_length=1)
    principal_id: str = Field(min_length=1)
    role: str = Field(description="university, faculty, department, lecturer or student.")
    password: str = Field(min_length=1)
    credential_id: str | None = None
    scope_unit_id: str | None = None


class ChangePasswordRequest(BaseModel):
    """Replacing your own password, having proved the old one."""

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)


class ResetPasswordRequest(BaseModel):
    """Setting somebody's password without their old one. University-scoped."""

    model_config = ConfigDict(extra="forbid")

    new_password: str = Field(min_length=1)


class SetCredentialActiveRequest(BaseModel):
    """Turning a login on or off."""

    model_config = ConfigDict(extra="forbid")

    is_active: bool
