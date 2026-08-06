"""Which persistence the suite runs against, and the machinery for running it on Postgres.

The whole point of Phase 6.1 is that this is the only file that has to know. Every context's
``conftest.py`` already called itself "the swap point"; this is what they swap *on*.

    pytest                                    # in-memory, the default everywhere
    UMS_TEST_BACKEND=postgres pytest          # the same tests, against a real database

When the backend is Postgres and no database can be reached, the run **skips** rather than
failing. A developer with no Docker running should not be told their change broke something,
and the two commands above are both meant to be things anybody can type.

Domain tests take nothing from this file, so they pay none of its cost — no engine, no
truncation, no event loop beyond the one pytest-asyncio gives them. That is the same property
their own conftest docstrings claim: "a domain test that needed a repository would be evidence
that logic had leaked out of the domain layer".
"""

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from academic_records.adapters.outbound.postgres import metadata as academic_records_metadata
from admissions.adapters.outbound.postgres import metadata as admissions_metadata
from billing.adapters.outbound.postgres import metadata as billing_metadata
from course_catalog.adapters.outbound.postgres import metadata as course_catalog_metadata
from enrollment.adapters.outbound.postgres import metadata as enrollment_metadata
from faculty_department.adapters.outbound.postgres import metadata as faculty_department_metadata
from identity.adapters.outbound.postgres import metadata as identity_metadata
from persistence import engine_for
from student_profile.adapters.outbound.postgres import metadata as student_profile_metadata

MEMORY = "memory"
POSTGRES = "postgres"

DEFAULT_TEST_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/ums"
"""What ``docker compose up -d db`` at the repository root gives you, so the common case needs
no env. The port is published, so this reaches the same database the containers use."""

ALL_METADATA = (
    academic_records_metadata,
    admissions_metadata,
    billing_metadata,
    course_catalog_metadata,
    enrollment_metadata,
    faculty_department_metadata,
    identity_metadata,
    student_profile_metadata,
)
"""One ``MetaData`` per context, each in a Postgres schema of its own name.

Collected here and nowhere in ``src/``: a module that imported all eight would be a module
importing seven contexts it has no business knowing about. A composition root may; that is what
makes it one.
"""


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "postgres: exercises the Postgres adapters directly")


@pytest.fixture(scope="session")
def backend() -> str:
    """``memory`` or ``postgres``. The one switch this whole phase turns on."""
    chosen = os.environ.get("UMS_TEST_BACKEND", MEMORY).strip().lower()
    if chosen not in (MEMORY, POSTGRES):
        raise pytest.UsageError(
            f"UMS_TEST_BACKEND={chosen!r} is not one of {MEMORY!r} or {POSTGRES!r}"
        )
    return chosen


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.environ.get("UMS_TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


@pytest_asyncio.fixture(scope="session")
async def engine(backend: str, database_url: str) -> AsyncIterator[AsyncEngine]:
    """The engine every Postgres repository in the run shares, with the schema built.

    Session-scoped: creating eight schemas and twenty-odd tables per test would dominate the
    run, and the tables do not change between tests. What changes between tests is the rows,
    and :func:`clean_database` deals with those.
    """
    if backend != POSTGRES:
        pytest.skip("this fixture is only meaningful against Postgres")

    engine = engine_for(database_url)
    try:
        async with engine.begin() as conn:
            for metadata in ALL_METADATA:
                await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{metadata.schema}"'))
            for metadata in ALL_METADATA:
                await conn.run_sync(metadata.create_all)
    except Exception as unreachable:
        await engine.dispose()
        pytest.skip(f"no Postgres at {database_url}: {unreachable}")

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def clean_database(backend: str, engine: AsyncEngine) -> AsyncIterator[None]:
    """An empty database for each test, in one statement.

    ``TRUNCATE`` of every table at once rather than per table, because Postgres will refuse a
    truncation that leaves a foreign key dangling and doing them together is also the fast
    path. ``RESTART IDENTITY`` matters more than it looks: the ``ordinal`` columns are what
    "in the order it was added" means, and a test asserting on ordering should not be able to
    pass because of what a previous test inserted.
    """
    if backend != POSTGRES:
        yield
        return

    tables = ", ".join(
        f'"{metadata.schema}"."{table.name}"'
        for metadata in ALL_METADATA
        for table in metadata.sorted_tables
    )
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def adapters(backend: str, request: pytest.FixtureRequest) -> Iterator["Adapters"]:
    """How a context's conftest asks for a repository without naming a storage.

    Each context's fixtures call ``adapters.faculties()`` and so on; this decides which class
    that builds. Postgres repositories are handed the session engine and a freshly truncated
    database, both requested lazily so an in-memory run never touches either.
    """
    if backend == MEMORY:
        yield Adapters(None)
        return
    request.getfixturevalue("clean_database")
    yield Adapters(request.getfixturevalue("engine"))


class Adapters:
    """A factory per repository port, resolving to whichever backend the run selected.

    Deliberately one object rather than fourteen fixtures: a context's conftest keeps its own
    fixture names, its own port annotations and its own docstrings, and the only line that
    changes is the constructor call. That is what "the tests themselves do not change" was
    always meant to protect.
    """

    def __init__(self, engine: AsyncEngine | None) -> None:
        self._engine = engine

    @property
    def is_postgres(self) -> bool:
        return self._engine is not None

    def _pick(self, in_memory: type, postgres: type) -> object:
        if self._engine is None:
            return in_memory()
        return postgres(self._engine)

    # ---- faculty & department ----

    def faculties(self) -> object:
        from faculty_department.adapters.outbound import InMemoryFacultyRepository
        from faculty_department.adapters.outbound.postgres import PostgresFacultyRepository

        return self._pick(InMemoryFacultyRepository, PostgresFacultyRepository)

    def departments(self) -> object:
        from faculty_department.adapters.outbound import InMemoryDepartmentRepository
        from faculty_department.adapters.outbound.postgres import PostgresDepartmentRepository

        return self._pick(InMemoryDepartmentRepository, PostgresDepartmentRepository)

    def programs(self) -> object:
        from faculty_department.adapters.outbound import InMemoryProgramRepository
        from faculty_department.adapters.outbound.postgres import PostgresProgramRepository

        return self._pick(InMemoryProgramRepository, PostgresProgramRepository)

    def lecturers(self) -> object:
        from faculty_department.adapters.outbound import InMemoryLecturerRepository
        from faculty_department.adapters.outbound.postgres import PostgresLecturerRepository

        return self._pick(InMemoryLecturerRepository, PostgresLecturerRepository)

    def sessions(self) -> object:
        from faculty_department.adapters.outbound import InMemorySessionRepository
        from faculty_department.adapters.outbound.postgres import PostgresSessionRepository

        return self._pick(InMemorySessionRepository, PostgresSessionRepository)

    # ---- course catalog ----

    def courses(self) -> object:
        from course_catalog.adapters.outbound import InMemoryCourseRepository
        from course_catalog.adapters.outbound.postgres import PostgresCourseRepository

        return self._pick(InMemoryCourseRepository, PostgresCourseRepository)

    # ---- student profile ----

    def students(self) -> object:
        from student_profile.adapters.outbound import InMemoryStudentRepository
        from student_profile.adapters.outbound.postgres import PostgresStudentRepository

        return self._pick(InMemoryStudentRepository, PostgresStudentRepository)

    def sequences(self) -> object:
        from student_profile.adapters.outbound import InMemoryMatricSequenceRepository
        from student_profile.adapters.outbound.postgres import PostgresMatricSequenceRepository

        return self._pick(InMemoryMatricSequenceRepository, PostgresMatricSequenceRepository)

    # ---- admissions ----

    def applicants(self) -> object:
        from admissions.adapters.outbound import InMemoryApplicantRepository
        from admissions.adapters.outbound.postgres import PostgresApplicantRepository

        return self._pick(InMemoryApplicantRepository, PostgresApplicantRepository)

    def cycles(self) -> object:
        from admissions.adapters.outbound import InMemoryAdmissionCycleRepository
        from admissions.adapters.outbound.postgres import PostgresAdmissionCycleRepository

        return self._pick(InMemoryAdmissionCycleRepository, PostgresAdmissionCycleRepository)

    def requirements(self) -> object:
        from admissions.adapters.outbound import InMemoryProgramEntryRequirementRepository
        from admissions.adapters.outbound.postgres import (
            PostgresProgramEntryRequirementRepository,
        )

        return self._pick(
            InMemoryProgramEntryRequirementRepository,
            PostgresProgramEntryRequirementRepository,
        )

    def policies(self) -> object:
        from admissions.adapters.outbound import InMemoryAlternativeProgramPolicyRepository
        from admissions.adapters.outbound.postgres import (
            PostgresAlternativeProgramPolicyRepository,
        )

        return self._pick(
            InMemoryAlternativeProgramPolicyRepository,
            PostgresAlternativeProgramPolicyRepository,
        )

    # ---- enrollment ----

    def enrollments(self) -> object:
        from enrollment.adapters.outbound import InMemoryEnrollmentRepository
        from enrollment.adapters.outbound.postgres import PostgresEnrollmentRepository

        return self._pick(InMemoryEnrollmentRepository, PostgresEnrollmentRepository)

    def offerings(self) -> object:
        from enrollment.adapters.outbound import InMemoryCourseOfferingRepository
        from enrollment.adapters.outbound.postgres import PostgresCourseOfferingRepository

        return self._pick(InMemoryCourseOfferingRepository, PostgresCourseOfferingRepository)

    # ---- academic records ----

    def records(self) -> object:
        from academic_records.adapters.outbound import InMemoryAcademicRecordRepository
        from academic_records.adapters.outbound.postgres import (
            PostgresAcademicRecordRepository,
        )

        return self._pick(InMemoryAcademicRecordRepository, PostgresAcademicRecordRepository)

    # ---- identity ----

    def credentials(self) -> object:
        from identity.adapters.outbound import InMemoryCredentialRepository
        from identity.adapters.outbound.postgres import PostgresCredentialRepository

        return self._pick(InMemoryCredentialRepository, PostgresCredentialRepository)

    # ---- billing ----

    def accounts(self) -> object:
        from billing.adapters.outbound import InMemoryAccountRepository
        from billing.adapters.outbound.postgres import PostgresAccountRepository

        return self._pick(InMemoryAccountRepository, PostgresAccountRepository)

    def schedules(self) -> object:
        from billing.adapters.outbound import InMemoryFeeScheduleRepository
        from billing.adapters.outbound.postgres import PostgresFeeScheduleRepository

        return self._pick(InMemoryFeeScheduleRepository, PostgresFeeScheduleRepository)

    def intents(self) -> object:
        from billing.adapters.outbound import InMemoryPaymentIntentRepository
        from billing.adapters.outbound.postgres import PostgresPaymentIntentRepository

        return self._pick(InMemoryPaymentIntentRepository, PostgresPaymentIntentRepository)
