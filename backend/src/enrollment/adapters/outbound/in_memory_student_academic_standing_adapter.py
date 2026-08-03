"""The anti-corruption adapter behind ``StudentAcademicStandingPort``.

This is where Academic Records' model would be translated into ours — and the reason it is
*fed* data rather than reading that context directly is the dependency rule itself: no
module may import another context at any layer, adapters included (CLAUDE.md section 4).
Whatever sits on the other side of this port is reached over a boundary that is not a
Python import: in Phase 6 that is Academic Records' read-model or API, and this class is
replaced by one that speaks to it.

Two translations live here, and only here:

* **Grades to passes.** Over there a student's record is a history of graded courses. What
  crosses into Enrollment is a set of course ids they passed. Which letter grades count as
  a pass is a LASU grading-scale question (CLAUDE.md section 6) belonging to Academic
  Records, and a prerequisite rule written against letter grades would be this context
  quietly acquiring an opinion about it. When the scale is confirmed, it lands over there
  and behind this adapter — not in ``EligibilityRule``.
* **Probation to standing.** Academic Records determines probation from CGPA against a
  threshold. Enrollment receives the conclusion as an enum and never the number.

Nothing registered means no record, which is the honest answer for a fresher and is what
``AcademicStanding.unrecorded`` exists for.
"""

from collections.abc import Iterable

from enrollment.domain.facts import AcademicStanding, Standing
from enrollment.ports.student_academic_standing import StudentAcademicStandingPort


class InMemoryStudentAcademicStandingAdapter(StudentAcademicStandingPort):
    """Answers from a table registered up front, keyed by ``student_id``."""

    def __init__(self) -> None:
        self._standings: dict[str, AcademicStanding] = {}

    def register(
        self,
        student_id: str,
        passed_course_ids: Iterable[str] = (),
        standing: Standing = Standing.GOOD_STANDING,
    ) -> None:
        """Record what Academic Records would answer for one student.

        ``passed_course_ids`` and not grades: the translation from one to the other is the
        thing this adapter exists to own, and a caller handing over letter grades would be
        pushing that decision back across the boundary.
        """
        self._standings[student_id] = AcademicStanding(
            student_id=student_id,
            passed_course_ids=frozenset(passed_course_ids),
            standing=standing,
        )

    async def standing_for(self, student_id: str) -> AcademicStanding | None:
        return self._standings.get(student_id)
