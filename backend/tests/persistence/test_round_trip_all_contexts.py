"""Every aggregate that carries state a constructor cannot express, read back by a stranger.

The companion to ``test_round_trip.py``, which makes the same argument for Faculty &
Department: every other Postgres test reads through the repository that wrote, and that
repository holds an identity map, so it cannot tell a correct mapping from one that never
ran. These read through a *second* repository with an empty map.

The six ``restore`` classmethods are the reason this file exists. Each one sets state that no
transition on the aggregate would let a reader reach, and each one is therefore a place where
a wrong column, a lost enum or a re-derived value would be invisible until somebody's
transcript or ledger was wrong. So this asserts the things those methods promise: that a
status survives, that a letter grade is the one that was awarded rather than one recomputed
now, and that money comes back to the kobo.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from academic_records.adapters.outbound.postgres import PostgresAcademicRecordRepository
from academic_records.domain import AcademicRecord, Standing
from admissions.adapters.outbound.postgres import (
    PostgresAdmissionCycleRepository,
    PostgresAlternativeProgramPolicyRepository,
    PostgresApplicantRepository,
    PostgresProgramEntryRequirementRepository,
)
from admissions.domain import (
    AdmissionCycle,
    AlternativeProgramPolicy,
    Applicant,
    ApplicationStatus,
    BioData,
    ProgramEntryRequirement,
    SubjectGroup,
    UtmeResult,
    UtmeSubjectScore,
)
from billing.adapters.outbound.postgres import (
    PostgresAccountRepository,
    PostgresFeeScheduleRepository,
    PostgresPaymentIntentRepository,
)
from billing.domain import (
    Account,
    ChargeKind,
    FeeSchedule,
    Level,
    Money,
    PaymentIntent,
    PaymentIntentStatus,
    SessionFeeLine,
)
from enrollment.adapters.outbound.postgres import (
    PostgresCourseOfferingRepository,
    PostgresEnrollmentRepository,
)
from enrollment.domain import (
    CourseFacts,
    CourseOffering,
    Enrollment,
    EnrollmentStatus,
    SemesterOrdinal,
    Term,
)
from student_profile.adapters.outbound.postgres import PostgresStudentRepository
from student_profile.domain import BioData as StudentBioData
from student_profile.domain import Level as StudentLevel
from student_profile.domain import MatricNumber, Student

pytestmark = pytest.mark.postgres

SESSION = "sess-2026"
TERM = Term(session_id=SESSION, semester_id="sem-2026-1", ordinal=SemesterOrdinal.FIRST)


@pytest.fixture(autouse=True)
def only_on_postgres(backend: str) -> None:
    if backend != "postgres":
        pytest.skip("there is nothing to round-trip through an in-memory dict")


def a_utme_result() -> UtmeResult:
    return UtmeResult(
        (
            UtmeSubjectScore(subject="USE OF ENGLISH", score=70),
            UtmeSubjectScore(subject="MATHEMATICS", score=80),
            UtmeSubjectScore(subject="PHYSICS", score=65),
            UtmeSubjectScore(subject="CHEMISTRY", score=60),
        )
    )


def an_applicant(applicant_id: str = "app-0001") -> Applicant:
    return Applicant.apply(
        applicant_id, "prog-csc", SESSION, BioData(full_name="Adaeze Okonkwo"), a_utme_result()
    )


class TestStudentProfile:
    async def test_bio_data_survives_field_by_field(self, engine, clean_database) -> None:
        """Flattened into columns, so a lost one is a student the registry cannot contact."""
        student = Student(
            "stu-0001",
            MatricNumber("260591001"),
            StudentBioData(
                full_name="Adaeze Okonkwo",
                date_of_birth=date(2008, 4, 17),
                email="adaeze@lasu.edu.ng",
                phone_number="08012345678",
            ),
            "prog-csc-bsc",
            SESSION,
            StudentLevel(200),
            applicant_id="app-77",
        )
        await PostgresStudentRepository(engine).add(student)

        stored = await PostgresStudentRepository(engine).get("stu-0001")

        assert stored is not None
        assert stored.bio_data == student.bio_data
        assert stored.entry_level == StudentLevel(200)
        assert stored.applicant_id == "app-77"

    async def test_a_student_with_no_optional_bio_data_comes_back_with_none(
        self, engine, clean_database
    ) -> None:
        """A missing phone number must not become an empty string on the way through."""
        await PostgresStudentRepository(engine).add(
            Student(
                "stu-0002",
                MatricNumber("260591002"),
                StudentBioData(full_name="Chidi Nwosu"),
                "prog-csc-bsc",
                SESSION,
                StudentLevel(100),
            )
        )

        stored = await PostgresStudentRepository(engine).get("stu-0002")

        assert stored is not None
        assert stored.bio_data.date_of_birth is None
        assert stored.bio_data.email is None
        assert stored.bio_data.phone_number is None
        assert stored.applicant_id is None


class TestAdmissions:
    @pytest.mark.parametrize(
        "status",
        [
            ApplicationStatus.APPLIED,
            ApplicationStatus.SCREENED,
            ApplicationStatus.OFFERED,
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.DECLINED,
            ApplicationStatus.MATRICULATED,
            ApplicationStatus.NO_OFFER_AVAILABLE,
        ],
    )
    async def test_every_status_in_the_machine_survives(
        self, engine, clean_database, status: ApplicationStatus
    ) -> None:
        """Every one, because ``Applicant.restore`` is the only way back into most of them."""
        repository = PostgresApplicantRepository(engine)
        applicant = an_applicant()
        if status is not ApplicationStatus.APPLIED:
            applicant.screen()
        if status in {
            ApplicationStatus.OFFERED,
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.DECLINED,
            ApplicationStatus.MATRICULATED,
        }:
            applicant.offer("prog-mth")
        if status in {ApplicationStatus.ACCEPTED, ApplicationStatus.MATRICULATED}:
            applicant.accept()
        if status is ApplicationStatus.MATRICULATED:
            applicant.record_acceptance_fee_paid()
            applicant.matriculate()
        if status is ApplicationStatus.DECLINED:
            applicant.decline()
        if status is ApplicationStatus.NO_OFFER_AVAILABLE:
            applicant.record_no_offer()
        await repository.add(applicant)

        stored = await PostgresApplicantRepository(engine).get("app-0001")

        assert stored is not None
        assert stored.status is status

    async def test_the_offered_program_is_not_collapsed_into_the_applied_one(
        self, engine, clean_database
    ) -> None:
        """Two columns because there are two facts, and an alternative offer is the case."""
        applicant = an_applicant()
        applicant.screen()
        applicant.offer("prog-mth")
        await PostgresApplicantRepository(engine).add(applicant)

        stored = await PostgresApplicantRepository(engine).get("app-0001")

        assert stored is not None
        assert stored.applied_program_id == "prog-csc"
        assert stored.offered_program_id == "prog-mth"

    async def test_the_fee_cleared_flag_survives(self, engine, clean_database) -> None:
        """It gates matriculation. A flag lost in storage is a student who cannot matriculate."""
        applicant = an_applicant()
        applicant.screen()
        applicant.offer("prog-csc")
        applicant.accept()
        applicant.record_acceptance_fee_paid()
        await PostgresApplicantRepository(engine).add(applicant)

        stored = await PostgresApplicantRepository(engine).get("app-0001")

        assert stored is not None
        assert stored.is_fee_cleared is True
        stored.matriculate()

    async def test_the_utme_result_comes_back_intact(self, engine, clean_database) -> None:
        await PostgresApplicantRepository(engine).add(an_applicant())

        stored = await PostgresApplicantRepository(engine).get("app-0001")

        assert stored is not None
        assert stored.utme_result == a_utme_result()
        assert stored.utme_result.aggregate == 275
        assert stored.utme_result.score_for("MATHEMATICS") == 80

    async def test_a_claimed_place_is_persisted(self, engine, clean_database) -> None:
        repository = PostgresAdmissionCycleRepository(engine)
        cycle = AdmissionCycle.open("prog-csc", SESSION, 2)
        await repository.add(cycle)
        cycle.offer()
        await repository.save(cycle)

        stored = await PostgresAdmissionCycleRepository(engine).get("prog-csc", SESSION)

        assert stored is not None
        assert (stored.offers_made, stored.quota, stored.places_remaining) == (1, 2, 1)

    async def test_a_requirement_keeps_its_required_subjects_and_its_choices(
        self, engine, clean_database
    ) -> None:
        """Two kinds of demand, and collapsing them would admit or reject the wrong people."""
        await PostgresProgramEntryRequirementRepository(engine).add(
            ProgramEntryRequirement(
                "prog-csc",
                SESSION,
                required_subjects=["Use of English", "Mathematics", "Physics"],
                one_of_groups=[SubjectGroup(options=frozenset({"CHEMISTRY", "BIOLOGY"}))],
            )
        )

        stored = await PostgresProgramEntryRequirementRepository(engine).get("prog-csc", SESSION)

        assert stored is not None
        assert stored.required_subjects == frozenset({"USE OF ENGLISH", "MATHEMATICS", "PHYSICS"})
        assert len(stored.one_of_groups) == 1
        assert stored.one_of_groups[0].options == frozenset({"CHEMISTRY", "BIOLOGY"})

    async def test_several_one_of_groups_stay_separate_demands(
        self, engine, clean_database
    ) -> None:
        """Flattening them into one set would merge two questions into one."""
        await PostgresProgramEntryRequirementRepository(engine).add(
            ProgramEntryRequirement(
                "prog-mcb",
                SESSION,
                required_subjects=["Use of English", "Biology"],
                one_of_groups=[
                    SubjectGroup(options=frozenset({"CHEMISTRY"})),
                    SubjectGroup(options=frozenset({"PHYSICS", "MATHEMATICS"})),
                ],
            )
        )

        stored = await PostgresProgramEntryRequirementRepository(engine).get("prog-mcb", SESSION)

        assert stored is not None
        assert [group.options for group in stored.one_of_groups] == [
            frozenset({"CHEMISTRY"}),
            frozenset({"PHYSICS", "MATHEMATICS"}),
        ]

    async def test_a_fallback_chain_keeps_its_order(self, engine, clean_database) -> None:
        """Order is the whole content: re-ordering the list changes who ends up where."""
        await PostgresAlternativeProgramPolicyRepository(engine).add(
            AlternativeProgramPolicy.for_program(
                "prog-csc", SESSION, ["prog-mth", "prog-sta", "prog-phy"]
            )
        )

        stored = await PostgresAlternativeProgramPolicyRepository(engine).get("prog-csc", SESSION)

        assert stored is not None
        assert stored.alternatives == ("prog-mth", "prog-sta", "prog-phy")


class TestEnrollment:
    @pytest.mark.parametrize(
        "status",
        [EnrollmentStatus.REGISTERED, EnrollmentStatus.AWAITING_GRADE, EnrollmentStatus.FINALIZED],
    )
    async def test_every_registration_status_survives(
        self, engine, clean_database, status: EnrollmentStatus
    ) -> None:
        repository = PostgresEnrollmentRepository(engine)
        enrollment = Enrollment.register("enr-1", "stu-1", CourseFacts("csc-101", 3), TERM)
        if status is not EnrollmentStatus.REGISTERED:
            enrollment.await_grade()
        if status is EnrollmentStatus.FINALIZED:
            enrollment.finalize()
        await repository.add(enrollment)

        stored = await PostgresEnrollmentRepository(engine).get("enr-1")

        assert stored is not None
        assert stored.status is status

    async def test_the_term_comes_back_as_the_same_value_object(
        self, engine, clean_database
    ) -> None:
        """Stored as three columns; a lost ordinal would send Billing the wrong threshold."""
        await PostgresEnrollmentRepository(engine).add(
            Enrollment.register("enr-1", "stu-1", CourseFacts("csc-101", 3), TERM)
        )

        stored = await PostgresEnrollmentRepository(engine).get("enr-1")

        assert stored is not None
        assert stored.term == TERM
        assert stored.term.is_first_semester is True

    async def test_the_snapshotted_credit_units_are_not_re_read(
        self, engine, clean_database
    ) -> None:
        """The whole reason units are a column: a re-valued course must not rewrite a term."""
        await PostgresEnrollmentRepository(engine).add(
            Enrollment.register("enr-1", "stu-1", CourseFacts("csc-101", 3), TERM)
        )

        stored = await PostgresEnrollmentRepository(engine).get("enr-1")

        assert stored is not None
        assert stored.credit_units == 3

    async def test_a_carry_over_is_remembered_as_one(self, engine, clean_database) -> None:
        await PostgresEnrollmentRepository(engine).add(
            Enrollment.register(
                "enr-2",
                "stu-1",
                CourseFacts("mth-101", 4),
                TERM,
                is_carry_over=True,
            )
        )

        stored = await PostgresEnrollmentRepository(engine).get("enr-2")

        assert stored is not None
        assert stored.is_carry_over is True

    async def test_a_claimed_seat_is_persisted(self, engine, clean_database) -> None:
        repository = PostgresCourseOfferingRepository(engine)
        offering = CourseOffering.open("csc-101", TERM, 30)
        await repository.add(offering)
        offering.claim_seat()
        await repository.save(offering)

        stored = await PostgresCourseOfferingRepository(engine).get("csc-101", TERM)

        assert stored is not None
        assert (stored.seats_taken, stored.capacity, stored.seats_remaining) == (1, 30, 29)


class TestAcademicRecords:
    async def test_a_transcript_comes_back_line_for_line_and_in_order(
        self, engine, clean_database
    ) -> None:
        record = AcademicRecord.open("stu-1")
        record.record_grade(course_id="CSC101", semester_id="sem-1", score=75, credit_units=3)
        record.record_grade(course_id="MTH101", semester_id="sem-1", score=45, credit_units=4)
        record.record_grade(course_id="MTH101", semester_id="sem-2", score=68, credit_units=4)
        await PostgresAcademicRecordRepository(engine).add(record)

        stored = await PostgresAcademicRecordRepository(engine).get("stu-1")

        assert stored is not None
        assert [(g.course_id, g.semester_id, g.score) for g in stored.grades] == [
            ("CSC101", "sem-1", 75),
            ("MTH101", "sem-1", 45),
            ("MTH101", "sem-2", 68),
        ]

    async def test_the_letters_are_the_ones_that_were_awarded(self, engine, clean_database) -> None:
        """Stored rather than re-derived, so a scale change cannot rewrite an old transcript."""
        record = AcademicRecord.open("stu-1")
        record.record_grade(course_id="CSC101", semester_id="sem-1", score=75, credit_units=3)
        await PostgresAcademicRecordRepository(engine).add(record)

        stored = await PostgresAcademicRecordRepository(engine).get("stu-1")

        assert stored is not None
        assert stored.grades[0].letter == "A"
        assert stored.grades[0].grade_point == Decimal("5.0")

    async def test_the_cgpa_computes_to_the_same_figure_after_a_round_trip(
        self, engine, clean_database
    ) -> None:
        """The number a student is shown, and the number the probation rule reads."""
        record = AcademicRecord.open("stu-1")
        record.record_grade(course_id="CSC101", semester_id="sem-1", score=75, credit_units=3)
        record.record_grade(course_id="MTH101", semester_id="sem-1", score=45, credit_units=4)
        before = record.cgpa
        await PostgresAcademicRecordRepository(engine).add(record)

        stored = await PostgresAcademicRecordRepository(engine).get("stu-1")

        assert stored is not None
        assert stored.cgpa == before
        assert stored.standing is record.standing

    async def test_a_failing_record_still_reads_as_probation(self, engine, clean_database) -> None:
        record = AcademicRecord.open("stu-2")
        record.record_grade(course_id="CSC101", semester_id="sem-1", score=35, credit_units=3)
        await PostgresAcademicRecordRepository(engine).add(record)

        stored = await PostgresAcademicRecordRepository(engine).get("stu-2")

        assert stored is not None
        assert stored.standing is Standing.PROBATION

    async def test_a_correction_and_its_audit_entry_both_survive(
        self, engine, clean_database
    ) -> None:
        """A corrected grade with no record of the correction is the thing corrections avoid."""
        repository = PostgresAcademicRecordRepository(engine)
        record = AcademicRecord.open("stu-1")
        record.record_grade(course_id="CSC101", semester_id="sem-1", score=45, credit_units=3)
        await repository.add(record)
        record.correct_grade(
            course_id="CSC101",
            semester_id="sem-1",
            corrected_score=75,
            reason="marks transposed",
            authorized_by="Registrar",
        )
        await repository.save(record)

        stored = await PostgresAcademicRecordRepository(engine).get("stu-1")

        assert stored is not None
        assert stored.grades[0].score == 75
        assert stored.grades[0].letter == "A"
        assert len(stored.corrections) == 1
        assert stored.corrections[0].previous_score == 45
        assert stored.corrections[0].reason == "marks transposed"
        assert stored.corrections[0].authorized_by == "Registrar"

    async def test_a_line_corrected_keeps_its_place_in_the_transcript(
        self, engine, clean_database
    ) -> None:
        """ "A correction fixes a mark rather than re-sitting a course."""
        repository = PostgresAcademicRecordRepository(engine)
        record = AcademicRecord.open("stu-1")
        record.record_grade(course_id="CSC101", semester_id="sem-1", score=45, credit_units=3)
        record.record_grade(course_id="MTH101", semester_id="sem-1", score=60, credit_units=4)
        await repository.add(record)
        record.correct_grade(
            course_id="CSC101",
            semester_id="sem-1",
            corrected_score=75,
            reason="marks transposed",
            authorized_by="Registrar",
        )
        await repository.save(record)

        stored = await PostgresAcademicRecordRepository(engine).get("stu-1")

        assert stored is not None
        assert [grade.course_id for grade in stored.grades] == ["CSC101", "MTH101"]


class TestBilling:
    async def test_money_comes_back_to_the_kobo(self, engine, clean_database) -> None:
        """NUMERIC and never a float. A bursary reconciles against a gateway to the kobo."""
        account = Account.open("app-1", "prog-csc")
        account.raise_acceptance_fee(SESSION, Money(Decimal("20000.01")))
        await PostgresAccountRepository(engine).add(account)

        stored = await PostgresAccountRepository(engine).get("app-1")

        assert stored is not None
        assert stored.total_charged == Money(Decimal("20000.01"))

    async def test_an_allocation_is_restored_rather_than_recomputed(
        self, engine, clean_database
    ) -> None:
        """Which charge absorbed what was a decision. Reading it back must not re-decide."""
        repository = PostgresAccountRepository(engine)
        account = Account.open("app-1", "prog-csc")
        account.raise_acceptance_fee(SESSION, Money("20000"))
        account.raise_matriculation_fee(SESSION, Money("50000"))
        await repository.add(account)
        account.apply_payment(
            gateway_ref="ref-1",
            amount=Money("30000"),
            received_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        await repository.save(account)

        stored = await PostgresAccountRepository(engine).get("app-1")

        assert stored is not None
        acceptance = stored.charge_for(ChargeKind.ACCEPTANCE, SESSION)
        matriculation = stored.charge_for(ChargeKind.MATRICULATION, SESSION)
        assert acceptance is not None and acceptance.is_settled
        assert matriculation is not None
        assert matriculation.allocated == Money("10000")
        assert stored.acceptance_fee_settled is True
        assert stored.outstanding == Money("40000")

    async def test_a_credit_balance_survives_as_the_figure_it_was(
        self, engine, clean_database
    ) -> None:
        """Surplus is legal, and stored rather than derived."""
        repository = PostgresAccountRepository(engine)
        account = Account.open("app-2", "prog-csc")
        account.raise_acceptance_fee(SESSION, Money("20000"))
        await repository.add(account)
        account.apply_payment(
            gateway_ref="ref-2",
            amount=Money("25000"),
            received_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        await repository.save(account)

        stored = await PostgresAccountRepository(engine).get("app-2")

        assert stored is not None
        assert stored.credit_balance == Money("5000")
        assert stored.total_paid == Money("25000")

    async def test_a_duplicate_gateway_reference_is_still_a_no_op_after_a_round_trip(
        self, engine, clean_database
    ) -> None:
        """The idempotency invariant has to survive storage, or a retry doubles the ledger."""
        repository = PostgresAccountRepository(engine)
        account = Account.open("app-3", "prog-csc")
        account.raise_acceptance_fee(SESSION, Money("20000"))
        account.apply_payment(
            gateway_ref="ref-3",
            amount=Money("20000"),
            received_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        await repository.add(account)

        stored = await PostgresAccountRepository(engine).get("app-3")
        assert stored is not None
        stored.apply_payment(
            gateway_ref="ref-3",
            amount=Money("20000"),
            received_at=datetime(2026, 9, 2, tzinfo=UTC),
        )

        assert stored.total_paid == Money("20000")
        assert len(stored.payments) == 1

    async def test_a_linked_matric_number_resolves_the_same_ledger(
        self, engine, clean_database
    ) -> None:
        """The second index the port says the party-id abstraction costs."""
        repository = PostgresAccountRepository(engine)
        account = Account.open("app-4", "prog-csc")
        account.link_student_id("260591001")
        await repository.add(account)

        by_matric = await PostgresAccountRepository(engine).get("260591001")
        by_applicant = await PostgresAccountRepository(engine).get("app-4")

        assert by_matric is not None
        assert by_applicant is not None
        assert by_matric.party_id == by_applicant.party_id == "app-4"

    async def test_a_fee_schedule_comes_back_priced(self, engine, clean_database) -> None:
        await PostgresFeeScheduleRepository(engine).add(
            FeeSchedule.for_session(
                SESSION,
                acceptance_fee=Money("20000"),
                matriculation_fee=Money("50000"),
                session_fees=(
                    SessionFeeLine(program_id="prog-csc", level=Level(100), amount=Money("100000")),
                    SessionFeeLine(
                        program_id="prog-mcb", level=Level(200), amount=Money("120000.50")
                    ),
                ),
            )
        )

        stored = await PostgresFeeScheduleRepository(engine).get(SESSION)

        assert stored is not None
        assert stored.acceptance_fee == Money("20000")
        assert stored.session_fee_for("prog-csc", Level(100)) == Money("100000")
        assert stored.session_fee_for("prog-mcb", Level(200)) == Money("120000.50")
        assert stored.session_fee_for("prog-csc", Level(200)) is None

    @pytest.mark.parametrize(
        "status",
        [
            PaymentIntentStatus.INITIATED,
            PaymentIntentStatus.CONFIRMED,
            PaymentIntentStatus.FAILED,
        ],
    )
    async def test_every_intent_status_survives(
        self, engine, clean_database, status: PaymentIntentStatus
    ) -> None:
        opened = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
        intent = PaymentIntent.initiate(
            "ref-x", "app-1", Money("20000"), initiated_at=opened, ttl=timedelta(hours=2)
        )
        if status is PaymentIntentStatus.CONFIRMED:
            intent.confirm(amount=Money("20000"), at=opened)
        if status is PaymentIntentStatus.FAILED:
            intent.fail(reason="card declined", at=opened)
        await PostgresPaymentIntentRepository(engine).add(intent)

        stored = await PostgresPaymentIntentRepository(engine).get("ref-x")

        assert stored is not None
        assert stored.status is status
        assert stored.ttl == timedelta(hours=2)

    async def test_a_short_payment_keeps_both_amounts(self, engine, clean_database) -> None:
        """Asked for and actually moved are two facts, and one column could not say both."""
        opened = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
        intent = PaymentIntent.initiate("ref-short", "app-1", Money("20000"), initiated_at=opened)
        intent.confirm(amount=Money("15000"), at=opened)
        await PostgresPaymentIntentRepository(engine).add(intent)

        stored = await PostgresPaymentIntentRepository(engine).get("ref-short")

        assert stored is not None
        assert stored.amount == Money("20000")
        assert stored.confirmed_amount == Money("15000")
        assert stored.amount_matched is False

    async def test_only_open_intents_come_back_from_the_sweep(self, engine, clean_database) -> None:
        """Not "every stale intent" — staleness is the caller's judgement, not a WHERE clause."""
        repository = PostgresPaymentIntentRepository(engine)
        opened = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
        for index in range(3):
            await repository.add(
                PaymentIntent.initiate(f"ref-{index}", "app-1", Money("100"), initiated_at=opened)
            )
        settled = PaymentIntent.initiate("ref-done", "app-1", Money("100"), initiated_at=opened)
        settled.confirm(amount=Money("100"), at=opened)
        await repository.add(settled)

        open_intents = await PostgresPaymentIntentRepository(engine).all_initiated()

        assert [intent.reference for intent in open_intents] == ["ref-0", "ref-1", "ref-2"]
