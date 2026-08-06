"""Value objects and the shared construction guards used across this context.

The guards live here so that "an entity must never be constructible into an
invalid state" is enforced in one place rather than restated in every
``__post_init__``.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum

from faculty_department.domain.errors import (
    InvalidAcademicYearError,
    InvalidQualificationError,
    InvalidScoreError,
    MissingIdentifierError,
)

MIN_SCORE = 0
MAX_SCORE = 100

_MIN_START_YEAR = 1900
_MAX_START_YEAR = 2999

_MIN_QUALIFICATION_YEAR = 1900


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


class Rank(Enum):
    """Where a lecturer sits on the academic ladder.

    A confirmed institutional fact (CLAUDE.md section 6) rather than an inference: this is the
    Nigerian ladder as it was stated, and a rank invented here would be baked into every staff
    record. The values are the wire form, so adding one is a decision somebody makes rather
    than a rename that quietly changes an API.
    """

    PROFESSOR = "professor"
    READER = "reader"
    SENIOR_LECTURER = "senior lecturer"
    LECTURER_I = "lecturer I"
    LECTURER_II = "lecturer II"
    ASSISTANT_LECTURER = "assistant lecturer"
    GRADUATE_ASSISTANT = "graduate assistant"


class EmploymentStatus(Enum):
    """The terms a lecturer is employed on. Confirmed alongside :class:`Rank`."""

    FULL_TIME = "full-time"
    PART_TIME = "part-time"
    VISITING = "visiting"
    ADJUNCT = "adjunct"
    CONTRACT = "contract"
    SABBATICAL = "sabbatical"


@dataclass(frozen=True, order=True)
class Qualification:
    """A degree a lecturer holds, and where it came from.

    ``degree`` is deliberately **free text rather than an enum**. Degree names vary by
    institution and by era — ``M.Eng``, ``MBBS``, ``B.A. (Hons)`` — and an enum that rejected
    a real qualification would force whoever entered it to pick a wrong one, which is worse
    than no enum at all. ``Rank`` and ``EmploymentStatus`` are enums because the university
    defines those; nobody defines the set of degrees the world can award.

    ``year`` is the year awarded. It must be in the past, on ``BioData``'s argument about
    dates of birth: the one cross-field check that is honestly ours to make.
    """

    degree: str
    discipline: str
    institution: str
    year: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "degree", require_text(self.degree, "degree"))
        object.__setattr__(self, "discipline", require_text(self.discipline, "discipline"))
        object.__setattr__(self, "institution", require_text(self.institution, "institution"))
        if not isinstance(self.year, int) or isinstance(self.year, bool):
            raise InvalidQualificationError("a qualification's year must be a whole number")
        if not _MIN_QUALIFICATION_YEAR <= self.year <= date.today().year:
            raise InvalidQualificationError(
                f"a qualification cannot be dated {self.year}; expected a year between "
                f"{_MIN_QUALIFICATION_YEAR} and {date.today().year}"
            )

    def __str__(self) -> str:
        return f"{self.degree} {self.discipline}, {self.institution} ({self.year})"


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
