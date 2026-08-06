"""One guard on the seeder: what it wrote is really there, and it hangs together.

The seeder is the only code outside the test suite that constructs every aggregate in the
system, which makes it the first thing to break when a constructor changes — and it would
break silently, because nothing else imports it. This runs it against a real database and
reads the result back through *fresh* repositories with empty identity maps, so what is
asserted is what the columns hold rather than what the writing repository happens to
remember (``tests/persistence/test_round_trip.py`` makes the same argument at length).

The assertions are about **coherence across contexts**, because that is what a seeder can
get wrong that a unit test cannot catch: a claimed seat that does not match the
registrations written against it, a cycle whose ``offers_made`` nobody earned, a matric
number that resolves to nothing, a ledger that answers to only one of its two party ids.

Postgres only. There is nothing to seed in a dict.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from academic_records.adapters.outbound.postgres import PostgresAcademicRecordRepository
from academic_records.domain import Standing
from admissions.adapters.outbound.postgres import (
    PostgresAdmissionCycleRepository,
    PostgresApplicantRepository,
)
from admissions.domain import ApplicationStatus
from billing.adapters.outbound.postgres import (
    PostgresAccountRepository,
    PostgresFeeScheduleRepository,
)
from billing.domain import ChargeKind, Money
from billing.domain import Level as BillingLevel
from course_catalog.adapters.outbound.postgres import PostgresCourseRepository
from enrollment.adapters.outbound.postgres import (
    PostgresCourseOfferingRepository,
    PostgresEnrollmentRepository,
)
from identity.adapters.outbound.postgres import PostgresCredentialRepository
from identity.domain import Role as IdentityRole
from student_profile.adapters.outbound.postgres import PostgresStudentRepository
from student_profile.domain import MatricNumber

pytestmark = pytest.mark.postgres


def _seed_module() -> ModuleType:
    """Import ``scripts/seed.py`` by path.

    ``scripts/`` is deliberately not a package and deliberately not on the import path: it
    is outside ``src/`` so that a module touching all seven contexts cannot be mistaken for
    production code (see the fitness test's rule (b)). Importing it by file path is the
    price of that placement, and it is a cheap one.
    """
    path = Path(__file__).resolve().parents[2] / "scripts" / "seed.py"
    spec = importlib.util.spec_from_file_location("seed", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def seed() -> ModuleType:
    return _seed_module()


@pytest.fixture(autouse=True)
def only_on_postgres(backend: str) -> None:
    if backend != "postgres":
        pytest.skip("there is nothing to seed into a dict")


@pytest.fixture
async def seeded(engine, clean_database, seed: ModuleType):
    return await seed.seed_all(engine)


@pytest.fixture
async def matric_of(seeded, engine, seed: ModuleType) -> dict[str, str]:
    """Student Profile's own id -> the matric number the rest of the system knows them by."""
    students = PostgresStudentRepository(engine)
    numbers = {}
    for student_id in seed.STUDENT_IDS.values():
        student = await students.get(student_id)
        assert student is not None
        numbers[student_id] = student.matric_number.value
    return numbers


class TestItWrites:
    async def test_the_summary_counts_what_the_fixtures_describe(self, seeded, seed) -> None:
        assert seeded.counts["faculties"] == len(seed.FACULTIES)
        assert seeded.counts["courses"] == len(seed.COURSES)
        assert seeded.counts["applicants"] == len(seed.APPLICANTS)
        assert seeded.counts["students"] == len(seed.STUDENT_IDS)
        assert seeded.counts["enrollments"] == len(seed.ENROLLMENTS)

    async def test_the_unpriced_program_is_reported_rather_than_silently_skipped(
        self, seeded
    ) -> None:
        """The branch the missing fee line exists to exercise. Silence would be the bug."""
        assert any("no session fee on the schedule" in note for note in seeded.notes)


class TestTheGraphHangsTogether:
    async def test_a_student_resolves_by_the_matric_number_they_were_issued(
        self, seeded, engine, seed
    ) -> None:
        students = PostgresStudentRepository(engine)

        student = await students.find_by_matric_number(MatricNumber("260591001"))

        assert student is not None
        assert student.student_id == "stu-0001"
        assert student.applicant_id == "app-0001"

    async def test_the_matriculated_applicants_are_the_students(self, seeded, engine, seed) -> None:
        applicants = PostgresApplicantRepository(engine)
        students = PostgresStudentRepository(engine)

        for applicant_id, student_id in seed.STUDENT_IDS.items():
            applicant = await applicants.get(applicant_id)
            student = await students.find_by_applicant(applicant_id)

            assert applicant is not None
            assert applicant.status is ApplicationStatus.MATRICULATED
            assert student is not None
            assert student.student_id == student_id
            assert student.program_id == applicant.offered_program_id

    async def test_a_cycles_offers_made_equals_the_applicants_holding_places(
        self, seeded, engine, seed
    ) -> None:
        """A number nobody earned is the easiest thing for a seeder to write."""
        cycles = PostgresAdmissionCycleRepository(engine)

        for program_id in seed.ADMISSION_QUOTAS:
            expected = sum(
                1
                for fixture in seed.APPLICANTS
                if fixture.end_state in seed.HOLDS_A_PLACE
                and fixture.offered_program_id == program_id
            )
            cycle = await cycles.get(program_id, seed.SESSION_ID)

            assert cycle is not None
            assert cycle.offers_made == expected

    async def test_an_offerings_seats_taken_equals_the_registrations_against_it(
        self, seeded, engine, seed
    ) -> None:
        """The other half of the same claim, about a register rather than a quota."""
        offerings = PostgresCourseOfferingRepository(engine)

        for fixture in seed.OFFERINGS:
            expected = sum(
                1
                for enrollment in seed.ENROLLMENTS
                if (enrollment.course_id, enrollment.term) == (fixture.course_id, fixture.term)
            )
            offering = await offerings.get(fixture.course_id, fixture.term)

            assert offering is not None
            assert offering.seats_taken == expected

    async def test_a_registrations_snapshotted_units_match_the_catalog_it_was_read_from(
        self, matric_of, engine, seed
    ) -> None:
        courses = PostgresCourseRepository(engine)
        enrollments = PostgresEnrollmentRepository(engine)

        registered = await enrollments.list_for_student_in_term(
            matric_of["stu-0001"], seed.FIRST_TERM
        )

        assert len(registered) == 4
        for enrollment in registered:
            course = await courses.get(enrollment.course_id)
            assert course is not None
            assert enrollment.credit_units == course.credit_units

    async def test_no_student_carries_more_than_the_confirmed_credit_cap(
        self, matric_of, engine, seed
    ) -> None:
        enrollments = PostgresEnrollmentRepository(engine)

        for student_id in matric_of.values():
            for term in (seed.FIRST_TERM, seed.SECOND_TERM):
                registered = await enrollments.list_for_student_in_term(student_id, term)
                load = sum(enrollment.credit_units for enrollment in registered)
                assert load <= 24

    async def test_a_registration_is_keyed_by_the_id_that_resolves_a_ledger(
        self, matric_of, engine, seed
    ) -> None:
        """The bug this file exists to catch, in one assertion.

        ``BillingFinancialClearanceAdapter`` hands Enrollment's ``student_id`` to Billing as a
        party-id with no translation, so a registration seeded under Student Profile's own
        ``stu-0001`` would find no ledger, and *every* seeded student would read as not
        financially cleared — silently, because "no session-fee charge on record" is a
        legitimate answer rather than an error.
        """
        accounts = PostgresAccountRepository(engine)
        enrollments = PostgresEnrollmentRepository(engine)

        for term in (seed.FIRST_TERM, seed.SECOND_TERM):
            for student_id in matric_of.values():
                for enrollment in await enrollments.list_for_student_in_term(student_id, term):
                    assert await accounts.get(enrollment.student_id) is not None


class TestTheTranscriptsAreReal:
    async def test_a_transcript_comes_back_with_a_cgpa_and_a_standing(
        self, matric_of, engine
    ) -> None:
        records = PostgresAcademicRecordRepository(engine)

        record = await records.get(matric_of["stu-0001"])

        assert record is not None
        assert len(record.grades) == 4
        assert record.cgpa > 0
        assert record.standing is Standing.GOOD_STANDING

    async def test_one_student_is_on_probation_so_the_state_appears_in_the_data(
        self, matric_of, engine
    ) -> None:
        records = PostgresAcademicRecordRepository(engine)

        record = await records.get(matric_of["stu-0005"])

        assert record is not None
        assert record.standing is Standing.PROBATION

    async def test_the_correction_and_its_audit_entry_both_survived(
        self, matric_of, engine
    ) -> None:
        records = PostgresAcademicRecordRepository(engine)

        record = await records.get(matric_of["stu-0002"])

        assert record is not None
        grade = record.grade_for("csc-101", "sem-2026-1")
        assert grade is not None
        assert grade.score == 62
        assert len(record.corrections) == 1
        assert record.corrections[0].previous_score == 26

    async def test_a_graded_course_was_one_the_student_was_registered_for(
        self, seeded, engine, seed
    ) -> None:
        """A transcript line for a course nobody registered would be a fiction."""
        registered = {
            (enrollment.student_id, enrollment.course_id) for enrollment in seed.ENROLLMENTS
        }

        for student_id, course_id, _, _ in seed.GRADES:
            assert (student_id, course_id) in registered


class TestTheLedgersAddUp:
    async def test_an_account_resolves_by_both_of_its_party_ids(self, seeded, engine) -> None:
        """The applicant id it was opened under and the matric number it was later linked to."""
        accounts = PostgresAccountRepository(engine)

        by_applicant = await accounts.get("app-0001")
        by_matric = await PostgresAccountRepository(engine).get("260591001")

        assert by_applicant is not None
        assert by_matric is not None
        assert by_matric.party_id == by_applicant.party_id == "app-0001"

    async def test_the_fully_paid_account_has_its_session_charge_settled(
        self, seeded, engine, seed
    ) -> None:
        """What clearance reads is what is *allocated to the session charge*, never a total."""
        accounts = PostgresAccountRepository(engine)

        account = await accounts.get("app-0001")

        assert account is not None
        session_charge = account.charge_for(ChargeKind.SESSION, seed.SESSION_ID)
        assert session_charge is not None
        assert session_charge.allocated == seed.SESSION_FEE
        assert account.credit_balance == Money("5000")

    async def test_the_part_paid_account_stands_at_seventy_percent_of_the_session_fee(
        self, seeded, engine, seed
    ) -> None:
        """The boundary the clearance adapter reads: cleared for one semester, not for two."""
        accounts = PostgresAccountRepository(engine)

        account = await accounts.get("app-0002")

        assert account is not None
        session_charge = account.charge_for(ChargeKind.SESSION, seed.SESSION_ID)
        assert session_charge is not None
        # Cross-multiplied and never divided, the way the clearance adapter compares: a ratio
        # quantized to kobo would clear a student standing at 69.999% of the session fee.
        assert session_charge.allocated.amount * 10 == seed.SESSION_FEE.amount * 7

    async def test_the_unpriced_program_has_no_session_charge_at_all(
        self, seeded, engine, seed
    ) -> None:
        accounts = PostgresAccountRepository(engine)
        schedules = PostgresFeeScheduleRepository(engine)

        schedule = await schedules.get(seed.SESSION_ID)
        account = await accounts.get("app-0006")

        assert schedule is not None
        assert schedule.session_fee_for("prog-eee", BillingLevel(100)) is None
        assert account is not None
        assert account.charge_for(ChargeKind.SESSION, seed.SESSION_ID) is None
        assert account.acceptance_fee_settled is True

    async def test_every_payment_has_the_intent_that_produced_it(
        self, seeded, engine, seed
    ) -> None:
        """One reference across both aggregates is what makes the whole path idempotent."""
        from billing.adapters.outbound.postgres import PostgresPaymentIntentRepository

        accounts = PostgresAccountRepository(engine)
        intents = PostgresPaymentIntentRepository(engine)

        for applicant_id, payments in seed.PAYMENTS.items():
            account = await accounts.get(applicant_id)
            assert account is not None
            for payment in payments:
                intent = await intents.get(payment.gateway_ref)
                assert intent is not None
                assert intent.confirmed_amount == payment.amount
                assert account.payment_for(payment.gateway_ref) is not None


class TestRunningItTwice:
    async def test_the_second_run_refuses_rather_than_doubling_the_ledger(
        self, seeded, engine, seed
    ) -> None:
        """Without ``--reset`` a re-seed is a duplicate id, and the CLI says so first."""
        assert await seed.is_populated(engine) is True

        with pytest.raises(Exception):  # noqa: B017 — one per context; the type is not the point
            await seed.seed_all(engine)


class TestTheSeededCredentials:
    """Every unit can be logged into, and the passwords are the ones the summary printed.

    A seeder that wrote credentials nobody could authenticate with would look identical to one
    that worked, right up until somebody tried to log in — the rows would be there and the
    hashes would be well-formed. So this checks the only thing that matters about a credential:
    that the password verifies.
    """

    async def test_there_is_one_credential_per_unit(self, seeded, engine, seed) -> None:
        expected = (
            1  # the university
            + len(seed.FACULTIES)
            + len(seed.DEPARTMENTS)
            + len(seed.LECTURERS)
            + len(seed.STUDENT_IDS)
        )
        assert seeded.counts["credentials"] == expected
        assert len(await PostgresCredentialRepository(engine).all()) == expected

    async def test_every_seeded_password_actually_works(self, seeded, engine, seed) -> None:
        """Read back through a fresh repository, so the hash is the one the column holds."""
        credentials = PostgresCredentialRepository(engine)
        for credential in await credentials.all():
            assert credential.authenticate(seed.demo_password(credential.login_id)), (
                f"the seeded password for {credential.login_id!r} does not verify"
            )

    async def test_a_student_logs_in_with_their_matric_number(
        self, seeded, engine, matric_of
    ) -> None:
        """The confirmed rule, checked against the numbers the issuer actually produced."""
        credentials = PostgresCredentialRepository(engine)
        for student_id, matric_number in matric_of.items():
            credential = await credentials.find_by_login_id(matric_number)
            assert credential is not None, f"no credential for matric number {matric_number}"
            assert credential.principal_id == student_id
            assert credential.role is IdentityRole.STUDENT

    async def test_no_applicant_is_given_a_login(self, seeded, engine, seed) -> None:
        """There is no applicant role; auth.md records that as open rather than guessing one."""
        principals = {c.principal_id for c in await PostgresCredentialRepository(engine).all()}
        assert not principals & {fixture.applicant_id for fixture in seed.APPLICANTS}

    async def test_each_role_is_scoped_to_the_unit_it_names(self, seeded, engine, seed) -> None:
        credentials = {c.principal_id: c for c in await PostgresCredentialRepository(engine).all()}
        for faculty_id, _, _ in seed.FACULTIES:
            assert credentials[faculty_id].role is IdentityRole.FACULTY
            assert credentials[faculty_id].scope.unit_id == faculty_id
        for department_id, _, _, _ in seed.DEPARTMENTS:
            assert credentials[department_id].role is IdentityRole.DEPARTMENT
        for lecturer_id, _, _, _ in seed.LECTURERS:
            assert credentials[lecturer_id].role is IdentityRole.LECTURER


class TestItRefusesToSeedSomewhereReal:
    """The guard that arrived with the credentials, and the reason it arrived with them.

    Everything else this script writes is wrong data in the wrong place — recoverable and
    embarrassing. Working logins whose passwords are printed in the source are a way in, and
    that is a different kind of mistake to make by typo.

    These need no database, so they are the one class here that is not Postgres-only — the
    autouse skip above still applies, which is a small loss and not worth a second module.
    """

    @pytest.mark.parametrize(
        "url",
        [
            "postgresql+asyncpg://user:password@localhost:5432/ums",
            "postgresql+asyncpg://user:password@127.0.0.1:5432/ums",
            "postgresql+asyncpg://user:password@db:5432/ums",
        ],
    )
    def test_a_local_url_is_allowed(self, seed, url: str) -> None:
        assert seed.looks_local(url)
        assert seed._refuse_if_not_local(url, overridden=False) is None

    @pytest.mark.parametrize(
        "url",
        [
            "postgresql+asyncpg://user:password@db.example.edu:5432/ums",
            "postgresql+asyncpg://user:password@10.0.0.5:5432/ums",
            "postgresql+asyncpg://user:password@ums-staging.internal:5432/ums",
        ],
    )
    def test_a_remote_url_is_refused(self, seed, url: str) -> None:
        """An allowlist of hostnames, not a search for the word 'prod'.

        A blocklist would wave through staging, UAT, and every hostname nobody thought of.
        """
        assert not seed.looks_local(url)
        refusal = seed._refuse_if_not_local(url, overridden=False)
        assert refusal is not None
        assert "--i-know-this-is-not-local" in refusal

    def test_the_override_is_honoured(self, seed) -> None:
        url = "postgresql+asyncpg://user:password@db.example.edu:5432/ums"
        assert seed._refuse_if_not_local(url, overridden=True) is None
