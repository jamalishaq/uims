"""Transcript lines and the arithmetic over them.

Two things live here: :class:`CourseGrade`, one line of a student's record, and
:class:`Transcript`, a frozen view over a collection of them that knows how to average.
They are together because a transcript line has no meaning apart from the transcript, and
they are *apart from the aggregate* so that the arithmetic can be tested with no record,
no repository and no event — which is what the build playbook's hand-computed CGPA fixture
needs.

**GPA = Σ(grade point x credit units) / Σ(credit units)** — features.md section 8, and the
reason ``credit_units`` has to reach this context at all.

Three decisions are baked into the numbers this module produces:

* **``Decimal`` throughout, never ``float``.** A CGPA is arithmetic somebody checks by
  hand, and a figure that prints as 2.9599999999999995 cannot be checked by anybody.
* **Two decimal places, half up.** The reported figure, and the one the probation rule
  compares — see :class:`~academic_records.domain.probation.ProbationPolicy` for why the
  rule reads the rounded number rather than the raw ratio.
* **Every attempt counts.** A course failed and later passed is two lines and two
  contributions to the CGPA. **Confirmed with a human** (CLAUDE.md section 6): there is no
  replacement, no "best attempt", no supersession. It is worth noticing that this rule
  needs no code — it is what a plain sum over the lines does, and the alternatives are the
  ones that would have required some.

Semesters are ordered by first appearance and not sorted. ``GradeSubmitted`` carries a
``semester_id`` and no session, and the id is Faculty & Department's opaque key: parsing an
ordinal or a year out of its characters would be this context inventing a calendar it does
not own (CLAUDE.md section 3 puts the calendar in Faculty & Department). Arrival order is
the honest ordering, and the CGPA does not depend on it — a sum does not care what order it
is taken in, which is why "CGPA over multiple semesters" is answerable without one.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from academic_records.domain.errors import GradeNotRecordedError
from academic_records.domain.grading_scale import AwardedGrade, GradingScale
from academic_records.domain.values import require_credit_units, require_identifier, require_score

_CENTS = Decimal("0.01")
"""The precision a grade point average is reported to."""

ZERO_GPA = Decimal("0.00")


def _quantize(value: Decimal) -> Decimal:
    """Round to two decimal places, half up. One definition, used by every average here."""
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CourseGrade:
    """One line of a transcript: a course, a semester, and what the student got.

    Frozen, and every derived field is derived at construction from the scale rather than
    accepted from a caller. A line cannot exist saying 75 and C, or 38 and passed, because
    there is no way to build one that names the letter, the point or the pass separately
    from the score they come from. That is the *first* half of "finalized grades are
    immutable"; the second half is that
    :class:`~academic_records.domain.academic_record.AcademicRecord` will not replace a line
    it already holds except through a correction.

    ``credit_units`` is a snapshot of what the course was worth when the grade was
    recorded, for the reason :class:`~academic_records.domain.facts.CourseCredits` gives:
    a re-valued course must not rewrite a transcript that has already been issued.
    """

    course_id: str
    semester_id: str
    score: int
    credit_units: int
    letter: str
    grade_point: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "course_id", require_identifier(self.course_id, "course_id"))
        object.__setattr__(self, "semester_id", require_identifier(self.semester_id, "semester_id"))
        object.__setattr__(self, "score", require_score(self.score))
        object.__setattr__(
            self, "credit_units", require_credit_units(self.credit_units, "credit units")
        )

    @classmethod
    def award(
        cls,
        *,
        course_id: str,
        semester_id: str,
        score: int,
        credit_units: int,
        scale: GradingScale,
    ) -> "CourseGrade":
        """Grade ``score`` on ``scale`` and produce the transcript line.

        The only constructor anything outside this module should use: it is what makes the
        letter and the grade point unable to disagree with the score.
        """
        awarded = scale.grade_for(require_score(score))
        return cls(
            course_id=course_id,
            semester_id=semester_id,
            score=score,
            credit_units=credit_units,
            letter=awarded.letter,
            grade_point=awarded.grade_point,
        )

    @property
    def key(self) -> tuple[str, str]:
        """What identifies this line within a record: the course and the semester it was sat in.

        A course sat twice in two semesters is two lines with two keys, which is how a
        carry-over ends up counted twice without a rule saying so.
        """
        return (self.course_id, self.semester_id)

    @property
    def awarded(self) -> AwardedGrade:
        return AwardedGrade(letter=self.letter, grade_point=self.grade_point)

    @property
    def is_pass(self) -> bool:
        return self.grade_point > 0

    @property
    def quality_points(self) -> Decimal:
        """The line's weighted contribution: grade point x credit units."""
        return self.grade_point * self.credit_units

    def __str__(self) -> str:
        return f"{self.course_id} {self.semester_id} {self.score} {self.letter}"


class Transcript:
    """A student's graded lines, and every average that can be taken over them.

    A read-only view, built from lines rather than owning them: the record holds the
    lines, and hands them here whenever it is asked a question. Cheap to rebuild and
    impossible to get out of step with the record, which a cached CGPA on the aggregate
    would not be.
    """

    def __init__(self, grades: Iterable[CourseGrade]) -> None:
        self._grades = tuple(grades)
        if any(not isinstance(grade, CourseGrade) for grade in self._grades):
            raise TypeError("a transcript is made of CourseGrade lines")

    @property
    def grades(self) -> tuple[CourseGrade, ...]:
        """Every line, in the order it was recorded. A tuple: callers cannot write back."""
        return self._grades

    @property
    def is_empty(self) -> bool:
        return not self._grades

    @property
    def semester_ids(self) -> tuple[str, ...]:
        """The semesters this student has been graded in, in order of first appearance."""
        seen: dict[str, None] = {}
        for grade in self._grades:
            seen.setdefault(grade.semester_id, None)
        return tuple(seen)

    @property
    def total_units(self) -> int:
        """Every unit attempted, passed or not. The denominator of the CGPA."""
        return sum(grade.credit_units for grade in self._grades)

    @property
    def total_quality_points(self) -> Decimal:
        """The numerator of the CGPA: Σ(grade point x credit units)."""
        return sum((grade.quality_points for grade in self._grades), Decimal(0))

    @property
    def cgpa(self) -> Decimal:
        """The cumulative grade point average over every attempt, to two decimal places.

        An empty transcript averages to ``0.00``. No *persisted* record is ever empty — a
        record comes into existence to hold a grade, and the use case that opens one
        records the grade before it stores it — so this is the value of an object in the
        middle of being built rather than an assessment of anybody.
        """
        return self._average(self._grades)

    @property
    def passed_course_ids(self) -> frozenset[str]:
        """Every course passed on at least one attempt.

        The set Enrollment's prerequisite rule is ultimately answered from, and the reason
        a carry-over works: a course failed in one semester and passed in a later one is in
        here on the strength of the later line, while both lines go on counting towards the
        CGPA.
        """
        return frozenset(grade.course_id for grade in self._grades if grade.is_pass)

    def for_semester(self, semester_id: str) -> tuple[CourseGrade, ...]:
        """Every line recorded in one semester, in the order recorded."""
        semester_id = require_identifier(semester_id, "semester_id")
        return tuple(grade for grade in self._grades if grade.semester_id == semester_id)

    def semester_gpa(self, semester_id: str) -> Decimal:
        """The grade point average for one semester, to two decimal places.

        Raises:
            GradeNotRecordedError: nothing was graded in that semester. Asking for the GPA
                of a semester the student did not sit is a caller's mistake rather than a
                figure with a sensible default — ``0.00`` would be indistinguishable from
                a semester they sat and failed entirely.
        """
        lines = self.for_semester(semester_id)
        if not lines:
            raise GradeNotRecordedError(f"no grades are recorded for semester {semester_id!r}")
        return self._average(lines)

    def semester_gpas(self) -> Mapping[str, Decimal]:
        """Every semester's GPA, keyed by semester id, in order of first appearance."""
        return {semester_id: self.semester_gpa(semester_id) for semester_id in self.semester_ids}

    def _average(self, lines: tuple[CourseGrade, ...]) -> Decimal:
        units = sum(line.credit_units for line in lines)
        if units == 0:
            return ZERO_GPA
        points = sum((line.quality_points for line in lines), Decimal(0))
        return _quantize(points / units)

    def __len__(self) -> int:
        return len(self._grades)

    def __repr__(self) -> str:
        return f"Transcript({len(self._grades)} lines, cgpa={self.cgpa})"
