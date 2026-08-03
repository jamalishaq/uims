"""The composition root: the one module that knows all seven contexts, and the ASGI app.

Everything in ``src/`` up to this point has been careful never to know about more than one
bounded context. This file is where that stops being possible and starts being the job. Somebody
has to introduce Faculty & Department's event publisher to Billing's handler, hand Enrollment an
adapter that reads Course Catalog, and give the webhook verifier the secret out of the
environment — and because no context may import another (``tests/architecture/
test_dependency_rule.py`` rule (b)), that somebody must stand outside all of them.

**It is exempted from rule (b) by exact name**, as ``COMPOSITION_ROOT`` in that test. The
argument is the one ``tests/conftest.py`` has made since Phase 6.1: "a module that imported all
seven would be a module importing six contexts it has no business knowing about. A composition
root may; that is what makes it one." Until this phase the only composition root was a test
module. Now uvicorn needs one, so it moved into ``src/`` and the fitness test learned its name.

**A flat module rather than a package**, for ``persistence.py``'s reason: ``discover_contexts()``
finds contexts by looking for directories under ``src/`` with an ``__init__.py``, so a package
here would become an eighth context and break the ``EXPECTED_CONTEXTS`` assertion.

**It is the only module in ``src/`` that reads ``os.environ``.** Every secret, DSN and policy
table below arrives somewhere as a constructor argument — the webhook secret into
``WebhookSignatureVerifier``, the department-code register into the matric-number adapter, the
DSN into ``engine_for``. That is what has let every one of those things be chosen freely by a
test for six phases, and this file is where the real values are read instead.

**What it does not do is create the schema.** There is no ``metadata.create_all`` here. Tables
belong to migrations, and a process that quietly built its own schema at startup would make a
deployment against a half-migrated database look healthy.
"""

import json
import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

import academic_records.adapters.inbound.http as academic_records_http
import admissions.adapters.inbound.http as admissions_http
import billing.adapters.inbound.http as billing_http
import course_catalog.adapters.inbound.http as course_catalog_http
import enrollment.adapters.inbound.http as enrollment_http
import faculty_department.adapters.inbound.http as faculty_department_http
import student_profile.adapters.inbound.http as student_profile_http
from academic_records.adapters.inbound import GRADE_SUBMITTED, GradeSubmittedHandler
from academic_records.adapters.outbound import CourseCatalogCourseCreditAdapter, CourseCredit
from academic_records.adapters.outbound.postgres import PostgresAcademicRecordRepository
from academic_records.application import CorrectGrade, ReadAcademicRecord, RecordSubmittedGrade
from admissions.adapters.outbound import FacultyDepartmentProgramInfoAdapter
from admissions.adapters.outbound import ProgramPlacement as AdmissionsProgramPlacement
from admissions.adapters.outbound.postgres import (
    PostgresAdmissionCycleRepository,
    PostgresAlternativeProgramPolicyRepository,
    PostgresApplicantRepository,
    PostgresProgramEntryRequirementRepository,
)
from admissions.application.make_offer_to_applicant import MakeOfferToApplicant
from admissions.application.screen_applicant import ScreenApplicant
from admissions.application.submit_application import SubmitApplication
from billing.adapters.inbound import (
    SESSION_OPENED,
    PaymentWebhookHandler,
    SessionOpenedHandler,
    WebhookSignatureVerifier,
)
from billing.adapters.outbound import InMemoryEventPublisher, StubPaymentGateway
from billing.adapters.outbound.postgres import (
    PostgresAccountRepository,
    PostgresFeeScheduleRepository,
    PostgresPaymentIntentRepository,
)
from billing.application.apply_session_fees import ApplySessionFees
from billing.application.confirm_payment import ConfirmPayment
from billing.application.initiate_payment import InitiatePayment
from billing.application.link_student_account import LinkStudentAccount
from billing.application.read_account import ReadAccount
from billing.application.reconcile_payment_intents import ReconcilePaymentIntents
from billing.application.record_payment import RecordPayment
from billing.application.views import AccountStatementView
from course_catalog.adapters.outbound.postgres import PostgresCourseRepository
from course_catalog.application.add_prerequisite import AddPrerequisite
from course_catalog.application.amend_course import AmendCourse
from course_catalog.application.list_department_courses import ListDepartmentCourses
from course_catalog.application.read_course import ReadCourse, ReadCourseCommand
from course_catalog.application.read_prerequisite_chain import ReadPrerequisiteChain
from course_catalog.application.register_course import RegisterCourse
from course_catalog.application.reinstate_course import ReinstateCourse
from course_catalog.application.remove_prerequisite import RemovePrerequisite
from course_catalog.application.retire_course import RetireCourse
from course_catalog.application.views import CourseView
from enrollment.adapters.outbound import (
    AcademicRecordsStandingAdapter,
    BillingFinancialClearanceAdapter,
    CourseCatalogCourseInfoAdapter,
    CourseRecord,
    SessionFeePosition,
    StudentRecord,
)
from enrollment.adapters.outbound.postgres import (
    PostgresCourseOfferingRepository,
    PostgresEnrollmentRepository,
)
from enrollment.application.register_for_course import RegisterForCourse
from faculty_department.adapters.outbound import InMemoryEventBus
from faculty_department.adapters.outbound.postgres import (
    PostgresDepartmentRepository,
    PostgresFacultyRepository,
    PostgresLecturerRepository,
    PostgresProgramRepository,
    PostgresSessionRepository,
)
from faculty_department.application.read_program_placement import ReadProgramPlacement
from faculty_department.application.submit_grade import SubmitGrade
from http_api import install_envelope_for_framework_errors, install_exception_handlers
from persistence import engine_for
from student_profile.adapters.outbound import FacultyDepartmentDepartmentCodeAdapter
from student_profile.adapters.outbound import ProgramPlacement as StudentProfileProgramPlacement
from student_profile.adapters.outbound.postgres import (
    PostgresMatricSequenceRepository,
    PostgresStudentRepository,
)
from student_profile.application.register_new_student import RegisterNewStudent
from student_profile.domain.matric_number_issuer import MatricNumberIssuer

API_PREFIX = "/api/v1"
"""Versioned from the first release, because the second one cannot retrofit it."""


class Settings:
    """Everything this process needs from its environment, read once and validated here.

    Read at startup rather than at the point of use, so a misconfigured deployment fails while
    it is starting instead of the first time somebody pays a fee.
    """

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        env = os.environ if environ is None else environ
        self.database_url = env.get("DATABASE_URL", "")
        self.paystack_secret_key = env.get("PAYSTACK_SECRET_KEY", "")
        self.allowed_origins = _origins(env.get("ALLOWED_ORIGINS", "[]"))
        self.department_numeric_codes = _department_codes(env.get("DEPARTMENT_NUMERIC_CODES", "{}"))

    def require(self) -> "Settings":
        """Fail now, with a name, rather than at the first request that needs the value."""
        missing = [
            name
            for name, value in (
                ("DATABASE_URL", self.database_url),
                ("PAYSTACK_SECRET_KEY", self.paystack_secret_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"missing required environment variables: {', '.join(missing)}")
        return self


def _origins(raw: str) -> list[str]:
    """``ALLOWED_ORIGINS`` as ``.env.example`` writes it: a JSON array."""
    try:
        parsed = json.loads(raw)
    except ValueError as unreadable:
        raise RuntimeError(f"ALLOWED_ORIGINS is not valid JSON: {raw!r}") from unreadable
    if not isinstance(parsed, list) or not all(isinstance(origin, str) for origin in parsed):
        raise RuntimeError(f"ALLOWED_ORIGINS must be a JSON array of strings, got {raw!r}")
    return parsed


def _department_codes(raw: str) -> dict[str, str]:
    """The university's register of numeric department codes, as a JSON object.

    ``{"CSC": "0591"}``. Configuration and not a default, because a guess here is baked into
    every matric number ever issued — see the adapter that consumes it. An empty register is
    permitted and means no student can be registered until it is filled, which is the failure
    that is noticed rather than the one that is not.
    """
    try:
        parsed = json.loads(raw)
    except ValueError as unreadable:
        raise RuntimeError(f"DEPARTMENT_NUMERIC_CODES is not valid JSON: {raw!r}") from unreadable
    if not isinstance(parsed, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in parsed.items()
    ):
        raise RuntimeError("DEPARTMENT_NUMERIC_CODES must be a JSON object of string to string")
    return parsed


# ---- the cross-context sources -------------------------------------------------------------
#
# Each of these satisfies a Protocol declared by a consuming context's adapter, by calling a
# providing context's use case. They are the only objects in the system that touch two contexts,
# and they do the least a translation can do: fetch, and rename fields. Deciding what the answer
# *means* is the adapter's, in the context whose language it means it in.


class CourseCatalogSource:
    """Answers Enrollment's and Academic Records' questions about a course, from the catalog."""

    def __init__(self, read_course: ReadCourse) -> None:
        self._read_course = read_course

    async def course_record(self, course_id: str) -> CourseRecord | None:
        view = await self._course(course_id)
        if view is None:
            return None
        return CourseRecord(
            course_id=view.course_id,
            credit_units=view.credit_units,
            prerequisite_ids=view.prerequisite_ids,
            is_active=view.is_active,
        )

    async def course_credit(self, course_id: str) -> CourseCredit | None:
        """Note the absence of an ``is_active`` check: a retired course must still resolve here.

        CLAUDE.md section 3 — "a retired course must keep resolving here, because transcripts
        refer to courses no longer taught."
        """
        view = await self._course(course_id)
        if view is None:
            return None
        return CourseCredit(course_id=view.course_id, credit_units=view.credit_units)

    async def _course(self, course_id: str) -> CourseView | None:
        from course_catalog.application.errors import CourseNotFoundError

        try:
            course = await self._read_course.execute(ReadCourseCommand(course_id=course_id))
        except CourseNotFoundError:
            return None
        return CourseView.of(course)


class AcademicRecordsSource:
    """Answers Enrollment's question about a student's standing, from their record."""

    def __init__(self, read_academic_record: ReadAcademicRecord) -> None:
        self._read_academic_record = read_academic_record

    async def student_record(self, student_id: str) -> StudentRecord | None:
        record = await self._read_academic_record.find(student_id)
        if record is None:
            return None
        return StudentRecord(
            student_id=record.student_id,
            passed_course_ids=frozenset(record.passed_course_ids),
            standing=record.standing.value,
        )


class FacultyDepartmentSource:
    """Answers Admissions' and Student Profile's questions about a program, from the calendar.

    Two ``program_placement`` methods would be tidier than one returning two shapes, so this
    class has two named differently: each consuming adapter declares its own Protocol with its
    own idea of what a placement is, and satisfying both from one read is the point.
    """

    def __init__(self, read_program_placement: ReadProgramPlacement) -> None:
        self._read = read_program_placement

    async def admissions_placement(
        self, program_id: str, session_id: str
    ) -> AdmissionsProgramPlacement | None:
        placement = await self._read.find(program_id, session_id)
        if placement is None:
            return None
        return AdmissionsProgramPlacement(
            program_id=placement.program_id,
            is_admitting=placement.is_admitting,
            session_is_open=placement.session_is_open,
        )

    async def student_profile_placement(
        self, program_id: str, session_id: str
    ) -> StudentProfileProgramPlacement | None:
        placement = await self._read.find(program_id, session_id)
        if placement is None:
            return None
        return StudentProfileProgramPlacement(
            department_code=placement.department_code,
            session_start_year=placement.session_start_year,
        )


class _AdmissionsPlacementSource:
    """Adapts :class:`FacultyDepartmentSource` to Admissions' Protocol method name."""

    def __init__(self, source: FacultyDepartmentSource) -> None:
        self._source = source

    async def program_placement(
        self, program_id: str, session_id: str
    ) -> AdmissionsProgramPlacement | None:
        return await self._source.admissions_placement(program_id, session_id)


class _StudentProfilePlacementSource:
    """Adapts :class:`FacultyDepartmentSource` to Student Profile's Protocol method name."""

    def __init__(self, source: FacultyDepartmentSource) -> None:
        self._source = source

    async def program_placement(
        self, program_id: str, session_id: str
    ) -> StudentProfileProgramPlacement | None:
        return await self._source.student_profile_placement(program_id, session_id)


class BillingSessionFeeLedger:
    """Satisfies Enrollment's ``SessionFeeLedger`` from Billing's read model.

    ``BillingFinancialClearanceAdapter``'s docstring named this object before it existed: "a
    composition root today, a client against Billing's read model in Phase 6". This is that
    client, and the adapter did not change to receive it.

    The two figures are the session charge's ``amount`` and what has been ``allocated`` to it —
    never a total paid. Admission fees settle first and must not count towards registration.
    """

    SESSION_FEE = "session fee"

    def __init__(self, read_account: ReadAccount) -> None:
        self._read_account = read_account

    async def session_fee_for(self, party_id: str, session_id: str) -> SessionFeePosition | None:
        """Read the session charge through Billing's view, so what crosses is primitives.

        Projecting first rather than reaching into ``Charge.amount`` directly is the same rule
        every route follows: past the application boundary, money is the two-decimal string the
        domain quantized. ``SessionFeePosition`` then parses it back to a ``Decimal`` in
        Enrollment's own type — exactly, because the string is exact.
        """
        statement = await self._read_account.find(party_id)
        if statement is None:
            return None
        for charge in AccountStatementView.of(statement).charges:
            if charge.kind == self.SESSION_FEE and charge.session_id == session_id:
                return SessionFeePosition(
                    charged=Decimal(charge.amount),
                    settled=Decimal(charge.allocated),
                )
        return None


# ---- the object graph ----------------------------------------------------------------------


class PostgresRepositories:
    """Every repository in the system, against one engine.

    Method-for-method the same shape as ``Adapters`` in ``tests/conftest.py``, and deliberately
    so: :func:`build` asks for repositories by name and neither knows nor cares which storage
    answers. That is what lets the HTTP suite run the *whole application* against the in-memory
    adapters and against Postgres without a second wiring, exactly as every other suite does.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def faculties(self) -> Any:
        return PostgresFacultyRepository(self._engine)

    def departments(self) -> Any:
        return PostgresDepartmentRepository(self._engine)

    def programs(self) -> Any:
        return PostgresProgramRepository(self._engine)

    def lecturers(self) -> Any:
        return PostgresLecturerRepository(self._engine)

    def sessions(self) -> Any:
        return PostgresSessionRepository(self._engine)

    def courses(self) -> Any:
        return PostgresCourseRepository(self._engine)

    def students(self) -> Any:
        return PostgresStudentRepository(self._engine)

    def sequences(self) -> Any:
        return PostgresMatricSequenceRepository(self._engine)

    def applicants(self) -> Any:
        return PostgresApplicantRepository(self._engine)

    def cycles(self) -> Any:
        return PostgresAdmissionCycleRepository(self._engine)

    def requirements(self) -> Any:
        return PostgresProgramEntryRequirementRepository(self._engine)

    def policies(self) -> Any:
        return PostgresAlternativeProgramPolicyRepository(self._engine)

    def enrollments(self) -> Any:
        return PostgresEnrollmentRepository(self._engine)

    def offerings(self) -> Any:
        return PostgresCourseOfferingRepository(self._engine)

    def records(self) -> Any:
        return PostgresAcademicRecordRepository(self._engine)

    def accounts(self) -> Any:
        return PostgresAccountRepository(self._engine)

    def schedules(self) -> Any:
        return PostgresFeeScheduleRepository(self._engine)

    def intents(self) -> Any:
        return PostgresPaymentIntentRepository(self._engine)


def build(app: FastAPI, repositories: Any, settings: Settings) -> None:
    """Wire every repository, adapter, use case and subscription onto ``app.state``.

    Built once at startup and shared for the life of the process. The repositories hold an
    identity map that ``MatricSequence.get_or_start`` depends on for correctness under
    concurrency (CLAUDE.md section 4), which is why they are not rebuilt per request. The cost
    is that the map grows for as long as the process runs; see the note in the phase write-up.

    ``repositories`` is anything with :class:`PostgresRepositories`' methods. Structural rather
    than typed, for ``SessionFeeLedger``'s reason: the test suite's factory lives outside
    ``src/`` and cannot be made to inherit from anything in here.
    """
    # -- faculty & department
    #
    # The faculty repository is not built, and its absence is a finding rather than an
    # oversight: no use case in the system reads a faculty. Faculties exist as an aggregate and
    # a table with nothing above them, which is the same gap that leaves this context with two
    # routes — see its router's docstring.
    departments = repositories.departments()
    programs = repositories.programs()
    lecturers = repositories.lecturers()
    sessions = repositories.sessions()

    bus = InMemoryEventBus()
    submit_grade = SubmitGrade(lecturers, sessions, bus)
    read_program_placement = ReadProgramPlacement(programs, departments, sessions)

    # -- course catalog
    courses = repositories.courses()
    read_course = ReadCourse(courses)

    # -- academic records
    records = repositories.records()
    catalog_source = CourseCatalogSource(read_course)
    record_submitted_grade = RecordSubmittedGrade(
        records, CourseCatalogCourseCreditAdapter(catalog_source)
    )
    read_academic_record = ReadAcademicRecord(records)
    correct_grade = CorrectGrade(records)

    # -- billing
    accounts = repositories.accounts()
    schedules = repositories.schedules()
    intents = repositories.intents()
    billing_events = InMemoryEventPublisher()

    read_account = ReadAccount(accounts)
    record_payment = RecordPayment(accounts, billing_events)
    confirm_payment = ConfirmPayment(intents, record_payment)
    reconcile_payment_intents = ReconcilePaymentIntents(
        intents, StubPaymentGateway(), confirm_payment
    )
    apply_session_fees = ApplySessionFees(accounts, schedules, billing_events)
    payment_webhook = PaymentWebhookHandler(
        WebhookSignatureVerifier(settings.paystack_secret_key), confirm_payment
    )

    # -- enrollment
    enrollments = repositories.enrollments()
    offerings = repositories.offerings()
    register_for_course = RegisterForCourse(
        enrollments,
        offerings,
        CourseCatalogCourseInfoAdapter(catalog_source),
        AcademicRecordsStandingAdapter(AcademicRecordsSource(read_academic_record)),
        BillingFinancialClearanceAdapter(BillingSessionFeeLedger(read_account)),
    )

    # -- admissions
    placement_source = FacultyDepartmentSource(read_program_placement)
    applicants = repositories.applicants()
    cycles = repositories.cycles()
    requirements = repositories.requirements()
    policies = repositories.policies()
    submit_application = SubmitApplication(
        applicants,
        FacultyDepartmentProgramInfoAdapter(_AdmissionsPlacementSource(placement_source)),
    )

    # -- student profile
    students = repositories.students()
    sequences = repositories.sequences()
    register_new_student = RegisterNewStudent(
        students,
        sequences,
        FacultyDepartmentDepartmentCodeAdapter(
            _StudentProfilePlacementSource(placement_source), settings.department_numeric_codes
        ),
        MatricNumberIssuer(),
    )

    # -- the subscriptions: the whole reason a composition root exists
    #
    # Two of the four handlers in the system are subscribed here and two are not, and the split
    # is not an omission.
    #
    # ``GradeSubmittedHandler`` and ``SessionOpenedHandler`` both expose ``on_message`` and both
    # have a publisher — ``SubmitGrade`` publishes ``GradeSubmitted`` on every submission, and
    # ``Session.open()`` produces ``SessionOpened``. Wiring them is real.
    #
    # ``OfferAcceptedHandler`` and ``StudentMatriculatedHandler`` deliberately have neither an
    # ``on_message`` nor a ``from_payload``, and their own docstrings say why: Admissions
    # publishes nothing yet, because it has no use case that accepts an offer or matriculates
    # anybody. Subscribing them would mean writing the deserialiser here — inventing the wire
    # shape of an event no publisher has ever emitted, in the one file that is supposed to
    # contain no opinions. CLAUDE.md section 3 makes the same call about the matric-number
    # link: "a handler for an event nobody publishes is wiring that can be neither right nor
    # wrong." What is missing is the publisher, and it is missing in Admissions rather than
    # here.
    #
    # **This has a consequence worth stating plainly.** ``OpenAccountForOffer`` is the only way
    # an ``Account`` is ever created, and it is reachable only from ``OfferAccepted``. With no
    # publisher there is no subscription, so in a running system no ledger is opened, and
    # everything downstream of a ledger — payments, clearance, registration — has nothing to
    # act on. That is not a defect of this wiring: it is the application-layer gap
    # (``Applicant.accept()`` has no use case in front of it) arriving where it becomes
    # visible. It is left visible rather than patched over with a route that opens accounts
    # directly, which would put a second, unguarded door into the ledger.
    bus.subscribe(GRADE_SUBMITTED, GradeSubmittedHandler(record_submitted_grade).on_message)
    bus.subscribe(SESSION_OPENED, SessionOpenedHandler(apply_session_fees).on_message)

    setattr(
        app.state,
        faculty_department_http.STATE_KEY,
        faculty_department_http.FacultyDepartmentDependencies(
            submit_grade=submit_grade, read_program_placement=read_program_placement
        ),
    )
    setattr(
        app.state,
        course_catalog_http.STATE_KEY,
        course_catalog_http.CourseCatalogDependencies(
            register_course=RegisterCourse(courses),
            amend_course=AmendCourse(courses),
            read_course=read_course,
            list_department_courses=ListDepartmentCourses(courses),
            retire_course=RetireCourse(courses),
            reinstate_course=ReinstateCourse(courses),
            add_prerequisite=AddPrerequisite(courses),
            remove_prerequisite=RemovePrerequisite(courses),
            read_prerequisite_chain=ReadPrerequisiteChain(courses),
        ),
    )
    setattr(
        app.state,
        academic_records_http.STATE_KEY,
        academic_records_http.AcademicRecordsDependencies(
            read_academic_record=read_academic_record, correct_grade=correct_grade
        ),
    )
    setattr(
        app.state,
        billing_http.STATE_KEY,
        billing_http.BillingDependencies(
            read_account=read_account,
            link_student_account=LinkStudentAccount(accounts),
            record_payment=record_payment,
            initiate_payment=InitiatePayment(accounts, intents),
            apply_session_fees=apply_session_fees,
            reconcile_payment_intents=reconcile_payment_intents,
            payment_webhook=payment_webhook,
        ),
    )
    setattr(
        app.state,
        enrollment_http.STATE_KEY,
        enrollment_http.EnrollmentDependencies(register_for_course=register_for_course),
    )
    setattr(
        app.state,
        admissions_http.STATE_KEY,
        admissions_http.AdmissionsDependencies(
            submit_application=submit_application,
            screen_applicant=ScreenApplicant(applicants, requirements),
            make_offer_to_applicant=MakeOfferToApplicant(
                applicants, cycles, requirements, policies
            ),
        ),
    )
    setattr(
        app.state,
        student_profile_http.STATE_KEY,
        student_profile_http.StudentProfileDependencies(register_new_student=register_new_student),
    )


# ---- the app -------------------------------------------------------------------------------

ROUTERS = (
    admissions_http,
    student_profile_http,
    course_catalog_http,
    faculty_department_http,
    enrollment_http,
    academic_records_http,
    billing_http,
)
"""One router per context, mounted in the order the playbook built the contexts."""


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI app. ``uvicorn src.main:app`` serves the module-level instance below."""
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved.require()
        engine = engine_for(resolved.database_url)
        build(app, PostgresRepositories(engine), resolved)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="University Management System",
        version="0.1.0",
        summary="Seven bounded contexts, one HTTP surface.",
        description=(
            "Hexagonal UMS API. Every route calls a use case and maps an application-layer "
            "view; no route touches a domain entity.\n\n"
            "**This API has no authentication.** Until an auth phase lands it must not be "
            "exposed to an untrusted network."
        ),
        lifespan=lifespan,
    )

    if resolved.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    install_envelope_for_framework_errors(app)
    for module in ROUTERS:
        app.include_router(module.router, prefix=API_PREFIX)
        install_exception_handlers(app, module.EXCEPTION_STATUSES)

    @app.get("/health", tags=["meta"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        """Says the process is up. It deliberately does not touch the database.

        A liveness probe that queried Postgres would take the API out of rotation for a
        database blip that ``resilient()`` was about to retry through.
        """
        return {"status": "ok"}

    return app


app = create_app()
"""The ASGI application. ``backend/Dockerfile`` serves this as ``src.main:app``."""
