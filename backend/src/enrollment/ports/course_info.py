"""Query port into Course Catalog, for the facts a registration is judged against.

Two things about a course have to be known before anybody can register for it: what it
requires first, and what it is worth. Neither is Enrollment's to know — courses belong to
Course Catalog (CLAUDE.md section 3) — and both are pulled synchronously because they are
needed to make a decision *now*. This is a query, not an event: waiting for a reply is
exactly the smell test CLAUDE.md section 3 gives for choosing a port over an event.

The return type is ours. :class:`CourseFacts` is expressed in Enrollment's own language and
no Course Catalog type appears anywhere in this file; the translation happens in the
adapter, which is the whole point of an anti-corruption layer. Over there a course is an
aggregate with a code, a title, an offering department and a retirement flag, and most of
that is none of this context's business. Three fields are, and one of them —
``is_active`` — arrives as a fact rather than as the status it is over there, because a
retired course is not a state Enrollment tracks, it is a reason to refuse.

Keyed by ``course_id`` alone, unlike this context's other lookups. A course's prerequisites
and credit units are slow-changing reference data with no session dimension, and a
registration snapshots the units it saw (see ``Enrollment.credit_units``) precisely because
this answer is the *current* one rather than the one that applied last year.
"""

from abc import ABC, abstractmethod

from enrollment.domain.facts import CourseFacts


class CourseInfoPort(ABC):
    """Reads what a course requires and what it is worth."""

    @abstractmethod
    def course_for(self, course_id: str) -> CourseFacts | None:
        """Return what is known about the course, or ``None`` if it is not known there.

        ``None`` is an answer, not a failure: asking about a course that does not exist is
        a question with a correct negative reply. It is also a different answer from a
        course that exists and has been retired — one is an id nobody recognises, the other
        is a real course no longer taught — and the application layer makes something of
        the difference.
        """
