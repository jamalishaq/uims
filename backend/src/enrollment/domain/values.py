"""Value objects and the shared construction guards used across this context.

The guards live here so that "an entity must never be constructible into an invalid
state" is enforced in one place rather than restated in every constructor. They duplicate
the guards in Admissions, Course Catalog, Faculty & Department and Student Profile by
design, not by oversight: a context may not import another context's domain models
(CLAUDE.md section 4), and the architecture fitness test enforces it.

``Term`` is the sharpest example of why the duplication is worth its cost. Faculty &
Department owns the academic calendar and models it as a ``Session`` aggregate with two
child ``Semester`` entities; what Enrollment needs is a single flat thing it can key a
registration by, compare, and hand to Billing. Our ``Term`` is that thing, and the two are
free to disagree — if the calendar over there ever grows a third semester or a summer
period, the translation changes in an adapter rather than here.

What this module deliberately does not do is judge anybody. Whether a load of 21 units may
grow by 3 is ``CreditLoadPolicy``'s arithmetic, but whether *this student* may register
*this course* is ``EligibilityRule``'s judgement, which reads several of these values at
once and is the only place all of them come together.
"""

from dataclasses import dataclass
from enum import Enum

from enrollment.domain.errors import (
    InvalidCreditLoadPolicyError,
    InvalidCreditUnitsError,
    InvalidTermError,
    MissingIdentifierError,
)

MAX_CREDIT_UNITS_PER_SEMESTER = 24
"""The most credit units a student may carry in one semester.

A settled institutional fact (CLAUDE.md section 6), in the manner of ``UTME_SUBJECT_COUNT``
and the matric number format: confirmed with a human rather than inferred. It is a default
here and a construction argument on :class:`CreditLoadPolicy`, so changing it — or varying
it by level, standing or program — is an argument at a call site, not an edit to a rule.
"""


def require_identifier(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank.

    Identifiers minted by other contexts — a course id, a student id, a semester id — are
    opaque to us: non-emptiness is the only thing we can honestly check.
    """
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be a non-empty identifier")
    return value.strip()


def require_text(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank."""
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be non-empty")
    return value.strip()


def require_credit_units(value: int, field: str = "credit units") -> int:
    """Return ``value``, rejecting anything that is not a whole, positive count of units.

    Zero is rejected: a course worth nothing would sit inside a student's load without
    ever moving it, and every cap and every GPA weighting downstream would have to decide
    for itself what that meant. ``True`` is an ``int`` to Python and a data-entry accident
    to a registry, so it is rejected explicitly.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidCreditUnitsError(f"{field} must be a whole number")
    if value <= 0:
        raise InvalidCreditUnitsError(f"{field} must be positive, got {value}")
    return value


class SemesterOrdinal(Enum):
    """Which half of the session a registration is for.

    Ours, not Faculty & Department's, though it says the same thing today. This context
    needs the ordinal for one reason: Billing's clearance rule differs between the two
    halves (CLAUDE.md section 3), and a registration that could not say which half it was
    for could not be cleared correctly.
    """

    FIRST = 1
    SECOND = 2


@dataclass(frozen=True)
class Term:
    """The registration period a student registers *in*: one semester of one session.

    Both ids, because both are needed and neither implies the other here. The session is
    what Billing charges against and what a transcript groups by; the semester is what a
    grade is submitted against (``GradeSubmitted`` carries ``semester_id``) and what a
    credit-load cap is measured over. Enrollment holds the pair rather than resolving one
    from the other, because resolving them means reading Faculty & Department's calendar,
    which is exactly the coupling this value object exists to avoid.

    Frozen and hashable, so it can key an offering and be compared for equality without
    anyone writing out the three-field comparison again.
    """

    session_id: str
    semester_id: str
    ordinal: SemesterOrdinal

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", require_identifier(self.session_id, "session_id"))
        object.__setattr__(self, "semester_id", require_identifier(self.semester_id, "semester_id"))
        if not isinstance(self.ordinal, SemesterOrdinal):
            raise InvalidTermError("term ordinal must be a SemesterOrdinal")

    @property
    def is_first_semester(self) -> bool:
        return self.ordinal is SemesterOrdinal.FIRST

    def __str__(self) -> str:
        return f"{self.session_id} semester {self.ordinal.value}"


@dataclass(frozen=True)
class CreditLoadPolicy:
    """How many credit units a student may carry in one term.

    A value object rather than a constant compared inline, so that the cap is a thing the
    university sets rather than a number a rule happens to contain. The same reasoning as
    ``MatricNumberFormat`` in Student Profile: a policy change should be a construction
    argument.

    Uniform across academic standings today. ``AcademicStanding`` carries the student's
    standing and this policy ignores it, deliberately and visibly: whether probation ought
    to lower the cap is an institutional fact nobody has confirmed (CLAUDE.md section 6),
    and inventing a reduced cap would quietly stop real students registering. When that
    answer arrives, it arrives as a second field here.
    """

    max_units: int = MAX_CREDIT_UNITS_PER_SEMESTER

    def __post_init__(self) -> None:
        if not isinstance(self.max_units, int) or isinstance(self.max_units, bool):
            raise InvalidCreditLoadPolicyError("credit load cap must be a whole number")
        if self.max_units <= 0:
            raise InvalidCreditLoadPolicyError(
                f"credit load cap must be positive, got {self.max_units}"
            )

    def permits(self, current_load: int, additional: int) -> bool:
        """Whether ``additional`` units may be added to a term already carrying ``current_load``."""
        return current_load + additional <= self.max_units

    def headroom(self, current_load: int) -> int:
        """Units still available in a term carrying ``current_load``. Never negative."""
        return max(self.max_units - current_load, 0)
