"""Value objects and the shared construction guards used across this context.

The guards live here so that "an entity must never be constructible into an invalid
state" is enforced in one place rather than restated in every constructor. They duplicate
the guards in Admissions, Course Catalog, Enrollment, Faculty & Department and Student
Profile by design, not by oversight: a context may not import another context's domain
models (CLAUDE.md section 4), and the architecture fitness test enforces it.

:func:`require_score` is the sharpest instance of that duplication. Faculty & Department
validates exactly the same range — because a score out of 100 is what a lecturer submits
and what this context receives. What the two do with it is where they part: over there a
score is checked and published and nothing more is asked of it, and here it is the input
to a grading scale. The scale is ours; the range is a coincidence, not a shared type.

A score stays a plain ``int`` here rather than becoming a value object of its own. Over in
Faculty & Department ``Score`` earns its keep as the thing a submission is validated
through; here every score entering the context passes through
:meth:`GradingScale.grade_for` within a line of arriving, and comes out the other side as
an :class:`~academic_records.domain.grading_scale.AwardedGrade` — which *is* the value
object, and is the one worth having.
"""

from academic_records.domain.errors import (
    InvalidCreditUnitsError,
    InvalidScoreError,
    MissingIdentifierError,
)

MIN_SCORE = 0
MAX_SCORE = 100


def require_identifier(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank.

    Identifiers minted by other contexts — a student id, a course id, a semester id — are
    opaque to us: non-emptiness is the only thing we can honestly check. A semester id in
    particular is never parsed here. It arrives on ``GradeSubmitted`` as Faculty &
    Department's own key, and a transcript that tried to read a session or an ordinal out
    of its characters would be this context inventing a calendar it does not own.
    """
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be a non-empty identifier")
    return value.strip()


def require_text(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank."""
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be non-empty")
    return value.strip()


def require_score(value: int, field: str = "score") -> int:
    """Return ``value``, rejecting anything that is not a whole mark out of 100.

    ``True`` is an ``int`` to Python and a data-entry accident to a registry, so it is
    rejected explicitly.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidScoreError(f"{field} must be a whole number")
    if not MIN_SCORE <= value <= MAX_SCORE:
        raise InvalidScoreError(f"{field} {value} is outside {MIN_SCORE}-{MAX_SCORE}")
    return value


def require_credit_units(value: int, field: str = "credit units") -> int:
    """Return ``value``, rejecting anything that is not a whole, positive count of units.

    Zero is rejected for the reason Enrollment rejects it: a course worth nothing would
    sit in a transcript contributing neither weight nor quality points, and every average
    computed over it would have to decide for itself what that meant.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidCreditUnitsError(f"{field} must be a whole number")
    if value <= 0:
        raise InvalidCreditUnitsError(f"{field} must be positive, got {value}")
    return value
