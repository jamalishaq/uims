"""Value objects and the shared construction guards used across this context.

The guards live here so that "an entity must never be constructible into an
invalid state" is enforced in one place rather than restated in every
``__post_init__``.
"""

from dataclasses import dataclass

from faculty_department.domain.errors import (
    InvalidAcademicYearError,
    InvalidScoreError,
    MissingIdentifierError,
)

MIN_SCORE = 0
MAX_SCORE = 100

_MIN_START_YEAR = 1900
_MAX_START_YEAR = 2999


def require_identifier(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank.

    Identifiers minted by other contexts (student, course, lecturer) are opaque
    to us: non-emptiness is the only thing we can honestly check.
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
    """Return ``value`` stripped and upper-cased. Codes are case-insensitive here."""
    return require_text(value, field).upper()


@dataclass(frozen=True, order=True)
class AcademicYear:
    """A session's academic year, identified by the year it starts in.

    ``AcademicYear(2026)`` is the 2026/2027 session.
    """

    start_year: int

    def __post_init__(self) -> None:
        if not isinstance(self.start_year, int) or isinstance(self.start_year, bool):
            raise InvalidAcademicYearError("academic year must be an integer starting year")
        if not _MIN_START_YEAR <= self.start_year <= _MAX_START_YEAR:
            raise InvalidAcademicYearError(
                f"academic year {self.start_year} is outside {_MIN_START_YEAR}-{_MAX_START_YEAR}"
            )

    @classmethod
    def from_label(cls, label: str) -> "AcademicYear":
        """Parse the conventional ``"2026/2027"`` form."""
        start, _, end = require_text(label, "academic year label").partition("/")
        if not start.isdigit() or not end.isdigit():
            raise InvalidAcademicYearError(f"{label!r} is not of the form '2026/2027'")
        year = cls(int(start))
        if int(end) != year.start_year + 1:
            raise InvalidAcademicYearError(f"{label!r} does not span consecutive years")
        return year

    @property
    def label(self) -> str:
        return f"{self.start_year}/{self.start_year + 1}"

    def __str__(self) -> str:
        return self.label


@dataclass(frozen=True, order=True)
class Score:
    """A raw examination score out of 100.

    This context validates the range and nothing more. Turning a score into a
    letter or a grade point is a grading scale, which Academic Records owns
    along with GPA/CGPA computation.
    """

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise InvalidScoreError("score must be an integer")
        if not MIN_SCORE <= self.value <= MAX_SCORE:
            raise InvalidScoreError(f"score {self.value} is outside {MIN_SCORE}-{MAX_SCORE}")
