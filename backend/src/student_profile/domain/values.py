"""Value objects and the shared construction guards used across this context.

The guards live here so that "an entity must never be constructible into an invalid
state" is enforced in one place rather than restated in every constructor.

They duplicate the guards in Faculty & Department and Course Catalog by design, not by
oversight. A context may not import another context's domain models (CLAUDE.md section
4), and the architecture fitness test enforces it. Two contexts agreeing today about
what a blank identifier is does not mean they must agree forever — the duplication is
what lets either one change its mind.
"""

from dataclasses import dataclass
from datetime import date

from student_profile.domain.errors import (
    InvalidBioDataError,
    InvalidDepartmentCodeError,
    InvalidEntryYearError,
    InvalidLevelError,
    MissingIdentifierError,
)

DEPARTMENT_CODE_DIGITS = 4
"""Width of the numeric department code carried by a matric number, e.g. ``0591``."""

LEVEL_STEP = 100

_MIN_ENTRY_YEAR = 1900
_MAX_ENTRY_YEAR = 2999


def require_identifier(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank.

    Identifiers minted by other contexts — a program id, a session id, an applicant id —
    are opaque to us: non-emptiness is the only thing we can honestly check.
    """
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be a non-empty identifier")
    return value.strip()


def require_text(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank."""
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be non-empty")
    return value.strip()


def require_optional_text(value: str | None, field: str) -> str | None:
    """Return ``value`` stripped, or ``None``. Absent is fine; blank is not.

    A student we hold no phone number for is a normal record. A student whose phone
    number is three spaces is a data-entry accident, and storing it would mean every
    later reader has to decide again whether that counts as a phone number.
    """
    if value is None:
        return None
    return require_text(value, field)


@dataclass(frozen=True)
class DepartmentCode:
    """A department's numeric code as it appears inside a matric number, e.g. ``0591``.

    Deliberately *not* the alphabetic ``CSC`` that Faculty & Department holds on its own
    ``Department``. This is Student Profile's own type, and the translation from whatever
    Faculty & Department publishes into these four digits happens in the adapter behind
    ``DepartmentCodePort`` — that is what the anti-corruption layer is for.

    Fixed width matters: the matric number is a run of digits with no separators, so a
    code of the wrong length would silently shift every other field.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidDepartmentCodeError("department code must be a string of digits")
        if len(self.value) != DEPARTMENT_CODE_DIGITS or not self.value.isdigit():
            raise InvalidDepartmentCodeError(
                f"department code {self.value!r} must be exactly {DEPARTMENT_CODE_DIGITS} digits"
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class EntryYear:
    """The calendar year a student's entry session starts in. ``EntryYear(2026)``.

    Stored in full, always. The matric number renders only the last two digits, which is
    lossy — 2026 and 2126 abbreviate alike — so the abbreviation is made where it is
    needed, by ``MatricNumberFormat``, and never held as if it were the year itself.
    """

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise InvalidEntryYearError("entry year must be an integer")
        if not _MIN_ENTRY_YEAR <= self.value <= _MAX_ENTRY_YEAR:
            raise InvalidEntryYearError(
                f"entry year {self.value} is outside {_MIN_ENTRY_YEAR}-{_MAX_ENTRY_YEAR}"
            )

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, order=True)
class Level:
    """An academic level: 100, 200, and so on.

    A positive multiple of 100 is the whole rule. There is deliberately no ceiling — how
    many levels a LASU program runs to is an institutional fact (CLAUDE.md section 6),
    and a maximum guessed here would start rejecting real students the first time a
    program ran longer than the guess.
    """

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise InvalidLevelError("level must be an integer")
        if self.value < LEVEL_STEP or self.value % LEVEL_STEP:
            raise InvalidLevelError(
                f"level {self.value} must be a positive multiple of {LEVEL_STEP}"
            )

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class BioData:
    """Who the student is, as far as this context is concerned.

    A name is required; everything else is optional, because a record that cannot be
    created without a phone number is a record that will be created with a fake one.

    No format is imposed on the email address or the phone number. Whether LASU writes
    ``+2348012345678`` or ``08012345678`` is an institutional fact, and a pattern guessed
    here would start rejecting real students. The one cross-field check that *is* ours to
    make is that nobody was born in the future.
    """

    full_name: str
    date_of_birth: date | None = None
    email: str | None = None
    phone_number: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "full_name", require_text(self.full_name, "full name"))
        object.__setattr__(self, "email", require_optional_text(self.email, "email"))
        object.__setattr__(
            self, "phone_number", require_optional_text(self.phone_number, "phone number")
        )
        if self.date_of_birth is None:
            return
        if not isinstance(self.date_of_birth, date):
            raise InvalidBioDataError("date of birth must be a date")
        if self.date_of_birth >= date.today():
            raise InvalidBioDataError(f"date of birth {self.date_of_birth} is not in the past")
