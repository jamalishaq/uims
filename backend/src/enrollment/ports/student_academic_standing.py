"""Query port into Academic Records, for what a student has already done.

A prerequisite rule is a question about the past, and this context holds none of it.
Academic Records owns grade history, GPA and probation determination (CLAUDE.md section 3),
and Enrollment asks it the narrowest possible version of what it needs: which courses has
this student passed, and how are they standing. Pulled synchronously, because a
registration cannot be decided without it.

The return type is ours, and the narrowing is the point. Over there a student's record is
grades, semesters, CGPA and a transcript; what comes back here is a set of course ids and
an enum. Enrollment deliberately does not receive grades: what counts as a pass is a
grading-scale question belonging to Academic Records (CLAUDE.md section 6 names the scale
as an institutional fact), and a prerequisite rule written against letter grades would be
this context quietly acquiring an opinion about it. The adapter turns grades into passes,
in one place, and that is where the scale change lands if the scale changes.

The traffic is one-way by design: Academic Records "never queries Enrollment; builds its
own model from events only". This port is Enrollment reading, not a conversation.
"""

from abc import ABC, abstractmethod

from enrollment.domain.facts import AcademicStanding


class StudentAcademicStandingPort(ABC):
    """Reads which courses a student has passed, and how they are standing."""

    @abstractmethod
    async def standing_for(self, student_id: str) -> AcademicStanding | None:
        """Return the student's standing, or ``None`` if no record is held there.

        ``None`` is an answer, not a failure, and it is the *common* answer at the moment
        it matters most: a fresher registering for their first semester has no academic
        record, because there is nothing to record until their first grade is submitted.
        The application layer reads that absence as ``AcademicStanding.unrecorded`` — a
        student who has passed nothing and been assessed by nobody — rather than as a
        reason to refuse, which would make the first registration of every student's life
        impossible.
        """
