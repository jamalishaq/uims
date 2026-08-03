"""Register one student for one course, if everything the university requires is true."""

from dataclasses import dataclass

from enrollment.application.errors import CourseNotFoundError, CourseOfferingNotFoundError
from enrollment.domain.course_offering import CourseOffering
from enrollment.domain.eligibility import EligibilityFailure, EligibilityReason, EligibilityRule
from enrollment.domain.enrollment import Enrollment
from enrollment.domain.errors import InvalidTermError
from enrollment.domain.facts import AcademicStanding, CourseFacts
from enrollment.domain.outcomes import SeatClaimed
from enrollment.domain.values import SemesterOrdinal, Term
from enrollment.ports.course_info import CourseInfoPort
from enrollment.ports.course_offering_repository import CourseOfferingRepositoryPort
from enrollment.ports.enrollment_repository import EnrollmentRepositoryPort
from enrollment.ports.financial_clearance import FinancialClearancePort
from enrollment.ports.student_academic_standing import StudentAcademicStandingPort


@dataclass(frozen=True)
class RegisterForCourseCommand:
    """One student's request to take one course, in primitives.

    Primitives and not value objects, for the reason ``SubmitApplicationCommand`` gives: a
    caller at the edge — an HTTP handler, a registry's bulk import — holds strings, and
    making it construct a ``Term`` first would put the domain's validation outside the use
    case that is supposed to run it.

    Nothing here says how many units the course is worth or whether it is a carry-over.
    A caller that could state either could state it wrongly, and the cap and the carry-over
    flag would be enforced against whatever the caller happened to believe. Both are looked
    up.

    ``semester_ordinal`` has no default. Billing's clearance rule differs between the two
    halves of a session, so a caller that omitted it would be asking about the wrong half
    and getting a confident answer.
    """

    enrollment_id: str
    student_id: str
    course_id: str
    session_id: str
    semester_id: str
    semester_ordinal: SemesterOrdinal

    @classmethod
    def of(
        cls,
        *,
        enrollment_id: str,
        student_id: str,
        course_id: str,
        session_id: str,
        semester_id: str,
        semester_ordinal: int,
    ) -> "RegisterForCourseCommand":
        """Build the command from an ordinal that is still an integer.

        The last field is the one this class could not make a primitive: an ordinal is 1 or 2
        and nothing else, and a caller passing 3 has to be told so somewhere. This is that
        somewhere. An HTTP adapter may not import ``SemesterOrdinal`` — rule (d) of the
        architecture fitness test — so without this it would either have to reach past the
        boundary or the boundary would have to accept an unchecked integer and discover the
        problem three calls later, inside ``Term``.

        Raises:
            InvalidTermError: the ordinal names no semester of a session.
        """
        try:
            ordinal = SemesterOrdinal(semester_ordinal)
        except ValueError as unknown:
            permitted = ", ".join(str(member.value) for member in SemesterOrdinal)
            raise InvalidTermError(
                f"semester ordinal {semester_ordinal!r} names no semester; a session has "
                f"semesters {permitted}"
            ) from unknown
        return cls(
            enrollment_id=enrollment_id,
            student_id=student_id,
            course_id=course_id,
            session_id=session_id,
            semester_id=semester_id,
            semester_ordinal=ordinal,
        )


@dataclass(frozen=True)
class RegistrationAccepted:
    """The student is registered and a seat has been claimed for them.

    Carries the units so a caller can show a running total without adding up the term
    again, and ``is_carry_over`` because a registry looking at a list of registrations
    wants to see which of them are repeats.
    """

    enrollment_id: str
    student_id: str
    course_id: str
    term: Term
    credit_units: int
    is_carry_over: bool
    seats_remaining: int


@dataclass(frozen=True)
class RegistrationRefused:
    """The student may not take this course, and here is everything standing in the way.

    ``reasons`` is never empty and holds *all* of them, not the first one found. A student
    refused for a missing prerequisite, who then sorts it out and is refused again for a
    full course, has queued twice for information the university had both times.
    """

    student_id: str
    course_id: str
    term: Term
    reasons: tuple[EligibilityFailure, ...]

    def has(self, reason: EligibilityReason) -> bool:
        """Whether the refusal includes a particular reason."""
        return any(failure.reason is reason for failure in self.reasons)


RegistrationOutcome = RegistrationAccepted | RegistrationRefused
"""Both ways a registration attempt can end. Neither is an exception; callers handle both."""


class RegisterForCourse:
    """Gather the facts, ask the domain, and record the answer.

    Orchestration only, and the split is CLAUDE.md section 3's: *other contexts supply
    facts, Enrollment owns the judgment*. This class fetches — the course from Course
    Catalog, the student's history from Academic Records, a yes-or-no from Billing, the
    offering and the term's existing registrations from its own repositories — and then
    asks ``EligibilityRule``. It compares nothing itself. Every rule stated here instead
    would be a rule stated twice the day a second registration path appears.

    **No transaction spans two aggregates** (CLAUDE.md section 4). The seat is claimed on
    the offering and saved; only then is the enrollment stored. The two writes are
    sequential and separate — see :meth:`_claim` for which way round the failure between
    them is allowed to fall, and why.

    Schedule-blind, permanently. Nothing here asks when the course meets or whether it
    clashes with another (CLAUDE.md section 3, *Deferred: Timetabling*): students register
    by eligibility, and the timetable is produced afterwards from these registrations.
    """

    def __init__(
        self,
        enrollments: EnrollmentRepositoryPort,
        offerings: CourseOfferingRepositoryPort,
        courses: CourseInfoPort,
        standings: StudentAcademicStandingPort,
        clearance: FinancialClearancePort,
        rule: EligibilityRule | None = None,
    ) -> None:
        self._enrollments = enrollments
        self._offerings = offerings
        self._courses = courses
        self._standings = standings
        self._clearance = clearance
        self._rule = rule or EligibilityRule()

    async def execute(self, command: RegisterForCourseCommand) -> RegistrationOutcome:
        """Decide the registration and record it.

        Returns:
            RegistrationAccepted: a seat was claimed and the student is registered.
            RegistrationRefused: at least one rule said no. Nothing was written — no seat
                claimed, no enrollment stored.

        Raises:
            CourseNotFoundError: Course Catalog does not recognise the course.
            CourseOfferingNotFoundError: the course is not being run this term.
            MissingIdentifierError: an identifier on the command was blank.
        """
        term = Term(
            session_id=command.session_id,
            semester_id=command.semester_id,
            ordinal=command.semester_ordinal,
        )

        course = await self._courses.course_for(command.course_id)
        if course is None:
            raise CourseNotFoundError(f"no course known with id {command.course_id!r}")

        offering = await self._offerings.get(course.course_id, term)
        if offering is None:
            raise CourseOfferingNotFoundError(
                f"course {course.course_id!r} is not being offered in {term}"
            )

        standing = await self._standings.standing_for(
            command.student_id
        ) or AcademicStanding.unrecorded(command.student_id)
        registered = await self._enrollments.list_for_student_in_term(command.student_id, term)

        failures = self._rule.unmet(
            course=course,
            offering=offering,
            standing=standing,
            current_load=sum(enrollment.credit_units for enrollment in registered),
            already_registered=any(
                enrollment.course_id == course.course_id for enrollment in registered
            ),
            is_financially_cleared=await self._clearance.is_cleared_for_registration(
                command.student_id, term
            ),
        )
        if failures:
            return self._refuse(command, course, term, failures)

        outcome = offering.claim_seat()
        if not isinstance(outcome, SeatClaimed):
            # The rule read this offering as having room a moment ago. Somebody else took
            # the last seat in between, which is the ordinary race a full course ends in —
            # so it becomes the refusal the rule would have made, not a crash.
            return self._refuse(
                command, course, term, (self._rule.capacity_failure(course, offering),)
            )

        enrollment = await self._claim(command, course, offering, term, standing)
        return RegistrationAccepted(
            enrollment_id=enrollment.enrollment_id,
            student_id=enrollment.student_id,
            course_id=enrollment.course_id,
            term=term,
            credit_units=enrollment.credit_units,
            is_carry_over=enrollment.is_carry_over,
            seats_remaining=offering.seats_remaining,
        )

    def _refuse(
        self,
        command: RegisterForCourseCommand,
        course: CourseFacts,
        term: Term,
        failures: tuple[EligibilityFailure, ...],
    ) -> RegistrationRefused:
        """Answer no, having written nothing. A refused registration leaves no trace."""
        return RegistrationRefused(
            student_id=command.student_id,
            course_id=course.course_id,
            term=term,
            reasons=failures,
        )

    async def _claim(
        self,
        command: RegisterForCourseCommand,
        course: CourseFacts,
        offering: CourseOffering,
        term: Term,
        standing: AcademicStanding,
    ) -> Enrollment:
        """Persist the claimed seat, then the student holding it. Two transactions.

        The order is deliberate, and it is chosen by which failure the university can live
        with — the same choice ``MakeOfferToApplicant`` makes about places. A crash between
        the two writes leaves the offering a seat short with nobody in it: the course
        under-enrols by one, a registrar can see it and give the seat out. The other order
        would leave a student registered against a seat that was never reserved, and a
        course that overfills has broken the invariant ``CourseOffering`` exists for — by
        the time anyone notices, there are more students than chairs in the room.

        ``is_carry_over`` is settled here rather than passed in: a course the student has
        attempted before and not passed is a carry-over, and that is a fact about their
        record, not something a caller may assert. Note that "attempted and failed" is
        read as "registered before and not among the courses passed" — Academic Records
        holds what was passed, and a course not in that set which the student is coming
        back to is exactly what CLAUDE.md section 5 calls a carry-over.
        """
        await self._offerings.save(offering)
        enrollment = Enrollment.register(
            enrollment_id=command.enrollment_id,
            student_id=command.student_id,
            course=course,
            term=term,
            is_carry_over=await self._is_carry_over(command.student_id, course, standing),
        )
        await self._enrollments.add(enrollment)
        return enrollment

    async def _is_carry_over(
        self, student_id: str, course: CourseFacts, standing: AcademicStanding
    ) -> bool:
        """Whether the student has been here before and not passed.

        Asked of the enrollment history rather than of Academic Records, because a failed
        course is not a fact Academic Records reports — it reports what was *passed*, and
        the absence of a course from that set says nothing on its own about whether it was
        ever taken. A previous registration that is not among the passes is a course
        attempted and not passed.
        """
        if standing.has_passed(course.course_id):
            return False
        return await self._enrollments.has_registered_before(student_id, course.course_id)
