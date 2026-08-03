"""The anti-corruption adapter behind ``CourseCreditPort``.

This is where Course Catalog's model would be translated into ours — and the reason it is
*fed* data rather than reading that context directly is the dependency rule itself: no
module may import another context at any layer, adapters included (CLAUDE.md section 4, and
the architecture fitness test enforces it). Whatever sits on the other side of this port is
reached over a boundary that is not a Python import: in Phase 6 that is Course Catalog's
read-model or API, and this class is replaced by one that speaks to it.

The translation that lives here is a narrowing so severe that it is almost the whole
adapter. A ``Course`` over there has a code, a title, an offering department, a
prerequisite chain and a retirement flag; one number off it reaches a transcript line.

**Retirement does not cross this boundary at all**, and the omission is deliberate. Course
Catalog retires courses instead of deleting them because transcripts refer to courses no
longer taught, and this is the port those transcripts are built through: a retired course
must keep answering here long after it has stopped being registrable in Enrollment, whose
own adapter *does* carry the flag. The same catalog fact matters on one side of the
university and not the other, which is what makes it a translation rather than a copy.
"""

from academic_records.domain.facts import CourseCredits
from academic_records.ports.course_credit import CourseCreditPort


class InMemoryCourseCreditAdapter(CourseCreditPort):
    """Answers from a table registered up front, keyed by ``course_id``."""

    def __init__(self) -> None:
        self._courses: dict[str, CourseCredits] = {}

    def register(self, course_id: str, credit_units: int) -> None:
        """Record what Course Catalog would answer for one course.

        Takes primitives rather than domain types so a caller does not have to import this
        context's domain to populate it, and so a course registered with nonsense units
        fails here rather than at the moment somebody's grade is being recorded.
        """
        self._courses[course_id] = CourseCredits(course_id=course_id, credit_units=credit_units)

    def credits_for(self, course_id: str) -> CourseCredits | None:
        return self._courses.get(course_id)
