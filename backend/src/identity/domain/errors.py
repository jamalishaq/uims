"""This context's domain exceptions.

One base, so an HTTP error table can map the family and then override the few that need a
different status — the arrangement ``http_api._status_for``'s MRO walk exists to support.
"""


class IdentityError(Exception):
    """Base for every refusal this context's domain makes."""


class MissingIdentifierError(IdentityError):
    """A credential id, principal id or scope id was blank."""


class InvalidLoginIdError(IdentityError):
    """The login id is not one this context will store.

    Blank, or carrying whitespace inside it. A login id is typed by a person into a field and
    then matched exactly; one with a space in the middle is a support ticket waiting to happen.
    """


class InvalidPasswordError(IdentityError):
    """The plaintext offered was not acceptable as a password."""


class InvalidPasswordHashError(IdentityError):
    """A stored hash was not in the format :class:`PasswordHash` writes.

    Raised on reconstitution, not on hashing. A row whose hash column holds something this
    context did not write is refused at the door rather than becoming a credential that can
    never authenticate and whose failure looks like a wrong password.
    """


class InvalidScopeError(IdentityError):
    """The scope does not describe anything this system can check a request against."""


class CredentialInactiveError(IdentityError):
    """The credential exists but has been deactivated.

    Distinct from "no such login id" *inside* the domain, and deliberately collapsed into one
    answer at the application boundary — see ``application/errors.py``.
    """
