"""The anti-corruption adapter behind ``CourseInfoPort``.

This is where Course Catalog's model would be translated into ours — and the reason it is
*fed* data rather than reading that context directly is the dependency rule itself: no
module may import another context at any layer, adapters included (CLAUDE.md section 4, and
the architecture fitness test enforces it). Whatever sits on the other side of this port is
reached over a boundary that is not a Python import: in Phase 6 that is Course Catalog's
read-model or API, and this class is replaced by one that speaks to it.

The translation that lives here is a narrowing. Over there a ``Course`` has a code, a
title, an offering department, a prerequisite list and an active flag; four of those are
none of Enrollment's business, and one of them changes name on the way across —
``Course.is_active`` is a catalog status, and what arrives here is a fact about whether the
course may be registered for. That the two coincide today is not a reason to let the word
travel.

Prerequisites arrive as the course's *direct* requirements, not a resolved chain. Course
Catalog can walk its own graph; Enrollment checks one level and relies on the fact that a
student who passed a course was held to its prerequisites when they registered for it.
"""

from collections.abc import Iterable

from enrollment.domain.facts import CourseFacts
from enrollment.ports.course_info import CourseInfoPort


class InMemoryCourseInfoAdapter(CourseInfoPort):
    """Answers from a table registered up front, keyed by ``course_id``."""

    def __init__(self) -> None:
        self._courses: dict[str, CourseFacts] = {}

    def register(
        self,
        course_id: str,
        credit_units: int,
        prerequisite_ids: Iterable[str] = (),
        *,
        active: bool = True,
    ) -> None:
        """Record what Course Catalog would answer for one course.

        Takes primitives rather than domain types so a caller does not have to import this
        context's domain to populate it, and so a course registered with nonsense units
        fails here rather than at the moment a student is trying to register. ``active`` is
        keyword-only because a bare boolean at a call site says nothing about which way
        round it goes.
        """
        self._courses[course_id] = CourseFacts(
            course_id=course_id,
            credit_units=credit_units,
            prerequisite_ids=tuple(prerequisite_ids),
            is_active=active,
        )

    def retire(self, course_id: str) -> None:
        """Record that Course Catalog has retired the course. It stays known, and stops being
        registrable — which is the whole distinction retirement exists to draw.
        """
        course = self._courses[course_id]
        self._courses[course_id] = CourseFacts(
            course_id=course.course_id,
            credit_units=course.credit_units,
            prerequisite_ids=course.prerequisite_ids,
            is_active=False,
        )

    async def course_for(self, course_id: str) -> CourseFacts | None:
        return self._courses.get(course_id)
