"""The matric number itself, and the format that composes one.

LASU writes a matric number as an unbroken run of digits — ``260591001`` is the first
student admitted into department ``0591`` for the ``2026/2027`` session:

    26      the entry year, last two digits
    0591    the department's numeric code
    001     the student's place in that department's intake for that year

The composition rule lives in :class:`MatricNumberFormat`, a value object, rather than
in the issuer. The widths above are an institutional fact (CLAUDE.md section 6); holding
them in a value means the day one of them changes is a day someone constructs the issuer
differently, not a day someone rewrites it.

Both fixed-width fields lead, so the trailing sequence may widen past its padding
without becoming ambiguous: a department's thousandth student of a year reads as
``2605911000``, and refusing to matriculate them would be the worse failure.
"""

from dataclasses import dataclass

from student_profile.domain.errors import InvalidMatricNumberError
from student_profile.domain.values import DepartmentCode, EntryYear

DEFAULT_YEAR_DIGITS = 2
DEFAULT_SEQUENCE_DIGITS = 3


@dataclass(frozen=True)
class MatricNumber:
    """A student's permanent identifier, e.g. ``260591001``.

    Validated as digits only. The *meaning* of those digits belongs to
    :class:`MatricNumberFormat`; a matric number issued under an older format must keep
    being a valid matric number, so nothing here parses the parts back out.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise InvalidMatricNumberError("matric number must be a non-empty string")
        if not self.value.isdigit():
            raise InvalidMatricNumberError(f"matric number {self.value!r} must be digits only")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class MatricNumberFormat:
    """How the entry year, department code and sequence combine into a matric number."""

    year_digits: int = DEFAULT_YEAR_DIGITS
    sequence_digits: int = DEFAULT_SEQUENCE_DIGITS

    def __post_init__(self) -> None:
        for field, width in (
            ("year_digits", self.year_digits),
            ("sequence_digits", self.sequence_digits),
        ):
            if not isinstance(width, int) or isinstance(width, bool) or width < 1:
                raise InvalidMatricNumberError(f"{field} must be a positive integer")
        if self.year_digits > 4:
            raise InvalidMatricNumberError("year_digits cannot exceed the four digits of a year")

    def render(
        self, department_code: DepartmentCode, entry_year: EntryYear, sequence: int
    ) -> MatricNumber:
        """Compose one matric number.

        ``sequence`` is a place in an intake, so it starts at 1: a zeroth student is a
        counter that was read before it was incremented, which is the bug this rejects.
        """
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise InvalidMatricNumberError(f"sequence {sequence!r} must be a positive integer")
        year = str(entry_year.value)[-self.year_digits :]
        return MatricNumber(f"{year}{department_code.value}{sequence:0{self.sequence_digits}d}")
