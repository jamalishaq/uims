"""The real adapter behind ``CourseInfoPort``: Course Catalog's answer, in Enrollment's words.

The shape is ``BillingFinancialClearanceAdapter``'s, for the same reason. No module under
``src/enrollment/`` may import ``course_catalog`` at any layer — rule (b) of the architecture
fitness test, which does not exempt ``if TYPE_CHECKING`` — so this class is *fed* rather than
reading the catalog itself. What feeds it is whoever stands outside both contexts: the
composition root, calling ``ReadCourse`` and handing back the four facts below.

**The translation lives here, not in the root.** :class:`CourseRecord` is a wire shape — four
primitives, no opinions — and turning it into a ``CourseFacts`` is this file's whole job. Put
that step in the composition root instead and it would be a translation performed outside the
context whose language it translates into, which is precisely what an anti-corruption layer is
supposed to prevent. The root's part is to *fetch*; deciding what a course means to Enrollment
is Enrollment's.

**Retirement crosses; retirement is not absence.** A retired course is reported with
``is_active=False`` rather than as ``None``, because the two mean different things to
``EligibilityRule``: an unknown course id is a mistake in the request, and a retired one is a
course that exists and may not be registered for. Answering ``None`` for both would turn the
second into ``CourseNotFoundError`` and tell a student their course does not exist.
"""

from dataclasses import dataclass
from typing import Protocol

from enrollment.domain.facts import CourseFacts
from enrollment.ports.course_info import CourseInfoPort


@dataclass(frozen=True)
class CourseRecord:
    """What a catalog has to say about a course, in primitives, before it means anything here.

    Deliberately not ``CourseFacts``: a source typed in this context's own domain language
    would push the translation out to whoever satisfies the protocol, and the point of the
    protocol is that the thing satisfying it knows nothing about Enrollment.
    """

    course_id: str
    credit_units: int
    prerequisite_ids: tuple[str, ...]
    is_active: bool


class CourseSource(Protocol):
    """Whatever can answer what a course is worth and what it requires first.

    Structural rather than an ABC, and that is the point: the object satisfying it lives
    outside this context and cannot inherit from anything in here without one context
    importing the other.
    """

    async def course_record(self, course_id: str) -> CourseRecord | None:
        """The course, or ``None`` if the catalog does not recognise the id."""
        ...


class CourseCatalogCourseInfoAdapter(CourseInfoPort):
    """Reads Course Catalog through a source, and answers in ``CourseFacts``."""

    def __init__(self, source: CourseSource) -> None:
        self._source = source

    async def course_for(self, course_id: str) -> CourseFacts | None:
        """The facts Enrollment judges a registration on, or ``None`` for an unknown course."""
        record = await self._source.course_record(course_id)
        if record is None:
            return None
        return CourseFacts(
            course_id=record.course_id,
            credit_units=record.credit_units,
            prerequisite_ids=record.prerequisite_ids,
            is_active=record.is_active,
        )
