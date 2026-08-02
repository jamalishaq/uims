"""Value objects and the shared construction guards used across this context.

The guards live here so that "an entity must never be constructible into an invalid
state" is enforced in one place rather than restated in every constructor.

These duplicate the guards in Faculty & Department by design, not by oversight. A
context may not import another context's domain models (CLAUDE.md section 4), and the
architecture fitness test enforces it. Two contexts agreeing today about what a blank
identifier is does not mean they must agree forever — the duplication is what lets
either one change its mind.
"""

from course_catalog.domain.errors import InvalidCreditUnitsError, MissingIdentifierError

MIN_CREDIT_UNITS = 1


def require_identifier(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank.

    Identifiers minted by other contexts — a department id, above all — are opaque to
    us: non-emptiness is the only thing we can honestly check.
    """
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be a non-empty identifier")
    return value.strip()


def require_text(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank."""
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be non-empty")
    return value.strip()


def require_code(value: str, field: str) -> str:
    """Return ``value`` stripped and upper-cased. Codes are case-insensitive here.

    No format is imposed. Whether LASU writes ``CSC101``, ``CSC 101`` or ``GST101H``
    is an institutional fact (CLAUDE.md section 6), and a pattern guessed here would
    start rejecting real courses the first time one of them did not fit.
    """
    return require_text(value, field).upper()


def require_credit_units(value: int, field: str) -> int:
    """Return ``value``, rejecting anything that is not a whole number of units.

    One unit is the floor: a course carrying no credit is not something this catalog
    can describe. There is deliberately no ceiling — a maximum credit load is an
    institutional fact, and guessing one would bake it into the model where a project
    or seminar course would later run into it.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidCreditUnitsError(f"{field} must be an integer")
    if value < MIN_CREDIT_UNITS:
        raise InvalidCreditUnitsError(f"{field} {value} is below {MIN_CREDIT_UNITS}")
    return value
