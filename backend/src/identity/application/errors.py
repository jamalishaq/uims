"""Failures the application layer raises, and the one place two facts become one answer."""


class ApplicationError(Exception):
    """Base for every refusal this context's use cases make."""


class AuthenticationFailedError(ApplicationError):
    """The login id and password together did not identify an active credential.

    **Three different domain facts collapse into this one type, on purpose:**

    - no credential holds that login id;
    - a credential does, and the password was wrong;
    - a credential does, the password was right, and it has been deactivated.

    The domain keeps them apart — ``Credential.authenticate`` raises for the third rather than
    answering ``False`` — because inside the model they are genuinely different things, and a
    future administrator's screen will want to say which. At the *boundary* they must be one
    answer with one message, because the difference between them is a user-enumeration oracle:
    an attacker who can tell "no such account" from "wrong password" can harvest valid login
    ids at their leisure, and in this system login ids are matric numbers and department codes,
    which are guessable in bulk.

    The timing is not equalised, and that is worth stating rather than leaving to be discovered:
    an unknown login id returns without hashing anything, and a known one pays for a scrypt
    derivation, so the two are distinguishable by a caller with a stopwatch. Closing that means
    hashing against a dummy credential on the miss path. It is a decision about how much a
    timing oracle costs here, recorded in ``auth.md`` rather than silently taken.
    """


class CredentialNotFoundError(ApplicationError):
    """An administrative read or write named a credential nobody holds.

    Distinct from :class:`AuthenticationFailedError` and safe to be distinct: reaching a route
    that raises this already required a university-scoped token, so the caller is entitled to
    know whether the thing they asked about exists.
    """


class LoginIdAlreadyIssuedError(ApplicationError):
    """A credential is being created with a login id somebody already logs in with."""


class PrincipalAlreadyHasCredentialError(ApplicationError):
    """The principal already has a credential, so a second would be a second live password.

    Answered rather than raised by the provisioning path — see ``register_credential.py`` — and
    kept as a type because an administrator creating one by hand should be told, not have their
    request quietly turn into a no-op.
    """


class UnknownRoleError(ApplicationError):
    """A credential was requested for a role this system does not have.

    Raised by the command rather than by Pydantic, because the route may not name the domain's
    enum (rule (d)) and a second enum in the schema would be a third vocabulary to keep in step
    with ``identity.domain.values.Role`` and ``security.Role``. The message lists what was
    allowed, which is the one thing a caller can act on.
    """
