"""What other contexts supply, said in Enrollment's own words.

These are the types the query ports answer in. They live in ``domain/`` rather than beside
the ports for two reasons. The first is that they are read by ``EligibilityRule``, and the
domain layer may not import ``ports/`` (CLAUDE.md section 4) — a fact object defined out
there would have to be translated a second time on the way in, and the second translation
is where the two copies drift apart. The second is that they are genuinely ours: the
ports merely carry them, and ``ports/`` importing ``domain/`` is the direction dependencies
already point.

Each of these is a deliberate narrowing of somebody else's model, which is what an
anti-corruption layer produces:

* Course Catalog's ``Course`` has a code, a title, an offering department and a
  prerequisite list. Registration cares about three of those and not the ones you would
  expect — the title never enters a decision, and the department decides nothing here.
* Academic Records holds grade history, GPA, CGPA and transcripts. Enrollment asks it one
  question — which courses has this student passed? — and gets back a set of ids, not
  grades. A grading scale is that context's business, and a prerequisite rule written
  against letter grades would be Enrollment quietly acquiring an opinion about what a pass
  is.

Nothing here judges anything. ``CourseFacts`` does not know whether its prerequisites are
satisfied and ``AcademicStanding`` does not know what a student may register; both are
handed to ``EligibilityRule``, which is the one place the judgement is made.
"""

from dataclasses import dataclass, field
from enum import Enum

from enrollment.domain.values import require_credit_units, require_identifier


@dataclass(frozen=True)
class CourseFacts:
    """What Enrollment needs to know about a course to decide a registration.

    ``is_active`` is the catalog's retirement flag reaching us as a fact rather than a
    status: Course Catalog retires courses instead of deleting them, because transcripts
    refer to courses no longer taught. A retired course keeps resolving for Academic
    Records and stops being registrable here, and this is the field that says so.

    ``prerequisite_ids`` are the course's *direct* prerequisites. Walking a chain is
    Course Catalog's ``PrerequisiteGraph``'s job; a student who passed a course was
    already held to that course's own prerequisites when they registered for it, so
    checking one level is checking the chain.
    """

    course_id: str
    credit_units: int
    prerequisite_ids: tuple[str, ...] = ()
    is_active: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "course_id", require_identifier(self.course_id, "course_id"))
        object.__setattr__(
            self, "credit_units", require_credit_units(self.credit_units, "credit units")
        )
        object.__setattr__(
            self,
            "prerequisite_ids",
            tuple(
                require_identifier(prerequisite_id, "prerequisite_id")
                for prerequisite_id in self.prerequisite_ids
            ),
        )
        object.__setattr__(self, "is_active", bool(self.is_active))


class Standing(Enum):
    """How a student is doing, as far as registration is concerned.

    Three values and not two. ``UNKNOWN`` is what a student Academic Records has never
    heard of gets, and it is a different thing from being in good standing: a fresher in
    their first semester has no record because there is nothing to record yet, and
    claiming they are in good standing would be this context inventing an assessment
    nobody made.
    """

    GOOD_STANDING = "good standing"
    PROBATION = "probation"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AcademicStanding:
    """What Academic Records knows about a student, reduced to what registration uses.

    ``passed_course_ids`` answers both questions Enrollment asks of a student's history:
    whether a prerequisite has been met, and whether a course being registered is a
    carry-over — a course previously attempted and not passed (CLAUDE.md section 5) — or a
    repeat of something already passed.

    ``standing`` is carried and, today, keyed off by nothing: the credit-load cap is
    uniform (see ``CreditLoadPolicy``). It is here because CLAUDE.md section 3 names it as
    one of the two facts this port supplies, and because the probation rule that will read
    it belongs to a conversation nobody has had yet.
    """

    student_id: str
    passed_course_ids: frozenset[str] = field(default_factory=frozenset)
    standing: Standing = Standing.GOOD_STANDING

    def __post_init__(self) -> None:
        object.__setattr__(self, "student_id", require_identifier(self.student_id, "student_id"))
        object.__setattr__(
            self,
            "passed_course_ids",
            frozenset(
                require_identifier(course_id, "course_id") for course_id in self.passed_course_ids
            ),
        )
        if not isinstance(self.standing, Standing):
            raise TypeError("standing must be a Standing")

    @classmethod
    def unrecorded(cls, student_id: str) -> "AcademicStanding":
        """A student Academic Records holds nothing for. Passed nothing, assessed by nobody.

        The honest reading of a port answering ``None``. A first-semester fresher must be
        able to register, and they will have no record until their first grade is
        submitted — treating the absence as a failure would make the first registration
        of every student's life impossible.
        """
        return cls(student_id=student_id, passed_course_ids=frozenset(), standing=Standing.UNKNOWN)

    def has_passed(self, course_id: str) -> bool:
        return course_id in self.passed_course_ids

    def unmet_prerequisites(self, course: CourseFacts) -> tuple[str, ...]:
        """The course's prerequisites this student has not passed, in the course's order."""
        return tuple(
            prerequisite_id
            for prerequisite_id in course.prerequisite_ids
            if prerequisite_id not in self.passed_course_ids
        )
