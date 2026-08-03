"""Query port into Course Catalog, for what a course is worth.

The one question this context asks anybody. ``GradeSubmitted`` carries a score and no
credit units, because Faculty & Department does not own credit units — Course Catalog
holds "course codes, titles, credit units, prerequisite chains, offering department"
(CLAUDE.md section 3). A CGPA is Σ(grade point x credit units) / Σ(credit units), so
without this port the numerator cannot be formed.

**Why a query and not an event.** CLAUDE.md section 3's smell test: "if you're polling
with queries to detect change, you wanted an event." Nothing here detects change. A grade
has arrived and a fact is needed *now* to turn it into a transcript line, which is the
definition of a pull. The alternative — Course Catalog publishing its credit units and
this context maintaining a mirror of them — would be a second copy of somebody else's
reference data, kept fresh so it could be read at a moment when a synchronous answer was
available anyway.

**Why this does not contradict "builds its own model from events only".** That sentence is
about the *record*: the grade history, the averages and the standing are assembled from
``GradeSubmitted`` and from nothing else, and in particular Academic Records never queries
Enrollment — a rule this port does not touch. What is pulled here is one number about a
course, read once and then snapshotted onto the line
(:class:`~academic_records.domain.facts.CourseCredits` says why), so the record does not
depend on this port a second time and a transcript issued years ago cannot be changed by
an amendment over in the catalog.

The return type is ours, and the narrowing is the point: a ``Course`` over there has a
code, a title, an offering department, a prerequisite chain and a retirement flag, and a
transcript line needs one number off it. There is deliberately no active flag —
retirement means "no longer registrable", which is Enrollment's concern; a retired course
must keep resolving here, because transcripts refer to courses no longer taught.
"""

from abc import ABC, abstractmethod

from academic_records.domain.facts import CourseCredits


class CourseCreditPort(ABC):
    """Reads what a course is worth in credit units."""

    @abstractmethod
    def credits_for(self, course_id: str) -> CourseCredits | None:
        """Return the course's credit units, or ``None`` if the catalog does not know it.

        ``None`` is not a reason to guess. A grade for a course whose worth cannot be
        established is refused by the application layer rather than recorded at some
        default weight — a line silently entered at three units would misstate the CGPA of
        the student it belongs to, and nothing downstream would ever flag it.
        """
