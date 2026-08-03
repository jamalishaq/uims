"""The one judgement of whether a student may register for a course.

Enrollment is a core domain because of this module. Three other contexts supply the facts —
Course Catalog what the course requires and is worth, Academic Records what the student has
passed, Billing whether they are cleared — and not one of them decides anything. The rule
that reads all of it together lives here, in the domain, where CLAUDE.md section 3 puts it:
*other contexts supply facts, Enrollment owns the judgment*. A use case that made these
comparisons itself would be the fat application service section 4 forbids, and the day a
second registration path appears — a bulk import, an administrative override — it would be
the day the rules were written down twice.

A domain service rather than a method on ``Enrollment``, and for a sharper reason than
``SubjectCombinationRule``'s: the judgement has to be made *before* an ``Enrollment``
exists. An aggregate cannot refuse its own construction on grounds it would need the
student's entire history and the offering's seat count to check.

Stateless. Everything it reasons about is passed in, so one instance can be shared and
none can go stale.

**Every failure is collected, not the first one.** A student refused for one reason, who
fixes it and is then refused for another, has been made to queue twice for information the
university had all along. This is why :meth:`permits` is defined in terms of :meth:`unmet`
rather than beside it — a rule that decided in one place and explained in another could
eventually decide one thing and explain the other.
"""

from dataclasses import dataclass
from enum import Enum

from enrollment.domain.course_offering import CourseOffering
from enrollment.domain.facts import AcademicStanding, CourseFacts
from enrollment.domain.values import CreditLoadPolicy


class EligibilityReason(Enum):
    """Why a registration was refused.

    Typed rather than prose so a caller can branch on the reason — an inbound adapter
    showing "pay your fees" needs to tell financial clearance from a missing prerequisite,
    and a message string is not something to write a condition against.
    """

    COURSE_NOT_ACTIVE = "course not active"
    PREREQUISITE_NOT_PASSED = "prerequisite not passed"
    ALREADY_PASSED = "already passed"
    ALREADY_REGISTERED = "already registered"
    CREDIT_LOAD_EXCEEDED = "credit load exceeded"
    COURSE_AT_CAPACITY = "course at capacity"
    NOT_FINANCIALLY_CLEARED = "not financially cleared"


@dataclass(frozen=True)
class EligibilityFailure:
    """One thing standing between a student and a course.

    ``detail`` is written for a person to read, and carries the numbers the decision was
    made on where there are any — "would take the term to 27 units, over the cap of 24"
    tells a student what to drop, where "credit load exceeded" only tells them to try
    again and find out.
    """

    reason: EligibilityReason
    detail: str

    def __str__(self) -> str:
        return self.detail


class EligibilityRule:
    """Judges one proposed registration against everything known about it."""

    def __init__(self, load_policy: CreditLoadPolicy | None = None) -> None:
        self._load_policy = load_policy or CreditLoadPolicy()

    @property
    def load_policy(self) -> CreditLoadPolicy:
        return self._load_policy

    def permits(
        self,
        *,
        course: CourseFacts,
        offering: CourseOffering,
        standing: AcademicStanding,
        current_load: int,
        already_registered: bool,
        is_financially_cleared: bool,
    ) -> bool:
        """Whether the registration may go ahead."""
        return not self.unmet(
            course=course,
            offering=offering,
            standing=standing,
            current_load=current_load,
            already_registered=already_registered,
            is_financially_cleared=is_financially_cleared,
        )

    def unmet(
        self,
        *,
        course: CourseFacts,
        offering: CourseOffering,
        standing: AcademicStanding,
        current_load: int,
        already_registered: bool,
        is_financially_cleared: bool,
    ) -> tuple[EligibilityFailure, ...]:
        """Every reason this registration cannot go ahead, in the order they are checked.

        Keyword-only throughout: six arguments of which two are booleans, and a call site
        that passed ``already_registered`` where ``is_financially_cleared`` was meant would
        be a silent inversion of two different refusals.

        The offering is read, never claimed. Taking the seat is
        :meth:`CourseOffering.claim_seat`'s to do and the use case's to order, because a
        rule that claimed as it judged would have to give the seat back every time it found
        a second problem.
        """
        failures: list[EligibilityFailure] = []

        if not course.is_active:
            failures.append(
                EligibilityFailure(
                    EligibilityReason.COURSE_NOT_ACTIVE,
                    f"course {course.course_id} has been retired from the catalog",
                )
            )

        # Registering something already registered this term is not a carry-over; it is the
        # same registration twice, and it would count its units against the cap twice.
        if already_registered:
            failures.append(
                EligibilityFailure(
                    EligibilityReason.ALREADY_REGISTERED,
                    f"student {standing.student_id} is already registered for "
                    f"course {course.course_id} this term",
                )
            )

        # A previously *failed* course is a carry-over and is exactly what re-registration
        # is for (CLAUDE.md section 5). A previously *passed* one is not: the student holds
        # the credit, and a second pass would be a second grade for one requirement.
        if standing.has_passed(course.course_id):
            failures.append(
                EligibilityFailure(
                    EligibilityReason.ALREADY_PASSED,
                    f"student {standing.student_id} has already passed course {course.course_id}",
                )
            )

        failures.extend(self._unmet_prerequisites(course, standing))

        if not self._load_policy.permits(current_load, course.credit_units):
            failures.append(
                EligibilityFailure(
                    EligibilityReason.CREDIT_LOAD_EXCEEDED,
                    f"course {course.course_id} would take the term to "
                    f"{current_load + course.credit_units} units, over the cap of "
                    f"{self._load_policy.max_units} "
                    f"({self._load_policy.headroom(current_load)} remaining)",
                )
            )

        if offering.is_full:
            failures.append(self.capacity_failure(course, offering))

        if not is_financially_cleared:
            failures.append(
                EligibilityFailure(
                    EligibilityReason.NOT_FINANCIALLY_CLEARED,
                    f"student {standing.student_id} has not been cleared to register "
                    f"for {offering.term}",
                )
            )

        return tuple(failures)

    def capacity_failure(self, course: CourseFacts, offering: CourseOffering) -> EligibilityFailure:
        """The refusal a full offering earns.

        Public, unlike the other failures, because a seat can go between the judgement and
        the claim: ``RegisterForCourse`` asks the offering for a seat after this rule has
        read it, and if somebody else took the last one in between, the student should be
        given the same sentence they would have been given a moment earlier. Two copies of
        that sentence would be two sentences before long.
        """
        return EligibilityFailure(
            EligibilityReason.COURSE_AT_CAPACITY,
            f"course {course.course_id} is full: all {offering.capacity} seats are taken",
        )

    def _unmet_prerequisites(
        self, course: CourseFacts, standing: AcademicStanding
    ) -> list[EligibilityFailure]:
        """One failure per prerequisite not passed, named individually.

        Named rather than counted because a student owed two prerequisites has two courses
        to go and find, and "prerequisites not met" would send them back to the catalog to
        work out which.

        Only the course's *direct* prerequisites are checked. Walking the chain is Course
        Catalog's ``PrerequisiteGraph``'s job, and it would be redundant here: a student
        who passed CSC201 was held to CSC101 when they registered for it.
        """
        return [
            EligibilityFailure(
                EligibilityReason.PREREQUISITE_NOT_PASSED,
                f"course {course.course_id} requires {prerequisite_id}, which "
                f"student {standing.student_id} has not passed",
            )
            for prerequisite_id in standing.unmet_prerequisites(course)
        ]
