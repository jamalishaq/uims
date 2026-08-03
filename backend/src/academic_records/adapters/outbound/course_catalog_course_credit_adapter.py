"""The real adapter behind ``CourseCreditPort``: what a course is worth, and nothing else.

Fed rather than reading Course Catalog directly — rule (b), the ``BillingFinancialClearanceAdapter``
pattern. The composition root calls ``ReadCourse`` and hands back the two fields below.

**Retirement deliberately does not cross this port.** CLAUDE.md section 3 is explicit: "a retired
course must keep resolving here, because transcripts refer to courses no longer taught." A
:class:`CourseCredit` has no ``is_active`` field for that reason, and a source that filtered
retired courses out would make a 2019 transcript unreadable the day its courses were withdrawn
from the catalog. This is the one place the asymmetry with Enrollment's ``CourseInfoPort`` — which
does carry the flag, because a registration must be refused — is visible, and it is intended.

The value read here is snapshotted onto the transcript line the moment the grade is recorded, so
a later re-valuation of the course cannot rewrite a transcript already issued. That makes this a
read taken once, at a known instant, rather than a lookup the CGPA depends on forever.
"""

from dataclasses import dataclass
from typing import Protocol

from academic_records.domain.facts import CourseCredits
from academic_records.ports.course_credit import CourseCreditPort


@dataclass(frozen=True)
class CourseCredit:
    """What a catalog has to say about a course's worth, in primitives."""

    course_id: str
    credit_units: int


class CourseCreditSource(Protocol):
    """Whatever can say how many credit units a course carries."""

    async def course_credit(self, course_id: str) -> CourseCredit | None:
        """The course's worth, or ``None`` if the catalog does not recognise the id."""
        ...


class CourseCatalogCourseCreditAdapter(CourseCreditPort):
    """Reads Course Catalog through a source, and answers in ``CourseCredits``."""

    def __init__(self, source: CourseCreditSource) -> None:
        self._source = source

    async def credits_for(self, course_id: str) -> CourseCredits | None:
        """What the course is worth, or ``None`` if it is not known there.

        ``None`` becomes ``CourseCreditsUnavailableError`` in the application layer rather than
        a guess: a grade recorded against units nobody could confirm is a CGPA quietly wrong for
        four years.
        """
        credit = await self._source.course_credit(course_id)
        if credit is None:
            return None
        return CourseCredits(course_id=credit.course_id, credit_units=credit.credit_units)
