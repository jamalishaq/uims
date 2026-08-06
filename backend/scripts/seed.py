"""Seed a development database with a coherent demo university.

Every Postgres adapter in this system has been exercised by tests and by nothing else: the
only code that creates the schema is a pytest fixture, and the only code that has ever
written an aggregate is the suite. Start the API against an empty database and every read
route answers with nothing, which makes the HTTP surface impossible to develop a frontend
against and impossible to demonstrate.

This writes one small university across all seven contexts so that those routes have
something to return.

**It writes through aggregates and repositories, never raw SQL** (CLAUDE.md section 4). The
tables encode decisions that an ``INSERT`` would silently get wrong: the ``ordinal`` columns
mean "the order this was added", the ``allocated`` figure on a charge records *which charge
absorbed which payment*, and the ``letter``/``grade_point`` on a transcript line are the ones
that were awarded rather than ones recomputed under today's scale.

**It lives outside ``src/``** because it touches all seven contexts, and rule (b) of
``tests/architecture/test_dependency_rule.py`` allows exactly one module in ``src/`` to do
that — ``main``, by exact name. ``scripts/`` is not scanned by the fitness test and is not in
``pyproject.toml``'s wheel packages, so this stays a development tool and never ships.

**It is not a migration and does not pretend to be one.** It creates the seven schemas and
the tables itself, in the shape ``tests/conftest.py`` does, because there is no Alembic
revision in this repository yet and this change does not close that gap.

Usage::

    docker compose up -d db
    uv run python scripts/seed.py --reset

Every amount, name, quota and department code below is a **demo fixture invented for this
script** — with one exception, marked where it appears — and none of it is an institutional
fact in the sense of CLAUDE.md section 6. Nothing here may be read back as a decision about
how LASU operates.
"""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

import academic_records.adapters.outbound.postgres as academic_records_postgres
import admissions.adapters.outbound.postgres as admissions_postgres
import billing.adapters.outbound.postgres as billing_postgres
import course_catalog.adapters.outbound.postgres as course_catalog_postgres
import enrollment.adapters.outbound.postgres as enrollment_postgres
import faculty_department.adapters.outbound.postgres as faculty_department_postgres
import student_profile.adapters.outbound.postgres as student_profile_postgres
from academic_records.adapters.outbound.postgres import PostgresAcademicRecordRepository
from academic_records.domain import AcademicRecord
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
    FeeSchedule,
    Money,
    PaymentIntent,
    SessionFeeLine,
)
from billing.domain import (
    Level as BillingLevel,
)
from course_catalog.adapters.outbound.postgres import PostgresCourseRepository
from course_catalog.domain import Course
from enrollment.adapters.outbound.postgres import (
    PostgresCourseOfferingRepository,
    PostgresEnrollmentRepository,
)
from enrollment.domain import (
    CourseFacts,
    CourseOffering,
    Enrollment,
    SeatClaimed,
    SemesterOrdinal,
    Term,
)
from faculty_department.adapters.outbound.postgres import (
    PostgresDepartmentRepository,
    PostgresFacultyRepository,
    PostgresLecturerRepository,
    PostgresProgramRepository,
    PostgresSessionRepository,
)
from faculty_department.domain import (
    AcademicYear,
    Department,
    Faculty,
    Lecturer,
    Program,
    Semester,
    Session,
)
from faculty_department.domain import (
    SemesterOrdinal as FacultySemesterOrdinal,
)
from persistence import engine_for
from student_profile.adapters.outbound.postgres import (
    PostgresMatricSequenceRepository,
    PostgresStudentRepository,
)
from student_profile.domain import (
    BioData as StudentBioData,
)
from student_profile.domain import (
    DepartmentCode,
    EntryYear,
    MatricNumberIssuer,
    Student,
)
from student_profile.domain import (
    Level as StudentLevel,
)

ALL_METADATA = (
    academic_records_postgres.metadata,
    admissions_postgres.metadata,
    billing_postgres.metadata,
    course_catalog_postgres.metadata,
    enrollment_postgres.metadata,
    faculty_department_postgres.metadata,
    student_profile_postgres.metadata,
)
"""One ``MetaData`` per context, in the order ``tests/conftest.py`` lists them."""

DEFAULT_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/ums"
"""What ``docker compose up -d db`` gives you — the same default, and for the same reason,
as ``tests/conftest.py``'s ``DEFAULT_TEST_DATABASE_URL``."""


# =========================================================================================
# Demo fixtures
# =========================================================================================
#
# INVENTED VALUES. Every figure, name, code and quota in this section was made up for this
# script. Fee amounts, quotas, entry requirements and level structures are institutional
# facts (CLAUDE.md section 6) and none of these are one — they exist so that a running
# system has something to show, and nothing downstream may treat them as confirmed.
#
# The single exception is CSC -> 0591 in DEPARTMENT_NUMERIC_CODES, which is the one numeric
# department code this repository has ever attested (CLAUDE.md section 6, and the matric
# number 260591001 it appears in). The other three digits-groups are invented alongside
# everything else here.

SESSION_ID = "sess-2026-2027"
SESSION_START_YEAR = 2026
FIRST_SEMESTER_ID = "sem-2026-1"
SECOND_SEMESTER_ID = "sem-2026-2"

FIRST_TERM = Term(
    session_id=SESSION_ID, semester_id=FIRST_SEMESTER_ID, ordinal=SemesterOrdinal.FIRST
)
SECOND_TERM = Term(
    session_id=SESSION_ID, semester_id=SECOND_SEMESTER_ID, ordinal=SemesterOrdinal.SECOND
)

DEPARTMENT_NUMERIC_CODES = {"CSC": "0591", "MTH": "0592", "PHY": "0593", "EEE": "0594"}
"""The register the matric-number adapter is fed. ``CSC`` is real; the rest are invented."""

ACCEPTANCE_FEE = Money("20000")
MATRICULATION_FEE = Money("50000")
SESSION_FEE = Money("150000")
ENTRY_LEVEL = 100

PAID_AT = datetime(2026, 8, 1, 10, 30, tzinfo=UTC)
"""One fixed instant for every seeded payment, so two runs produce identical rows."""

FACULTIES = (
    ("fac-sci", "Faculty of Science", "SCI"),
    ("fac-eng", "Faculty of Engineering", "ENG"),
)

DEPARTMENTS = (
    ("dept-csc", "fac-sci", "Computer Science", "CSC"),
    ("dept-mth", "fac-sci", "Mathematics", "MTH"),
    ("dept-phy", "fac-sci", "Physics", "PHY"),
    ("dept-eee", "fac-eng", "Electrical and Electronic Engineering", "EEE"),
)

PROGRAMS = (
    ("prog-csc", "dept-csc", "B.Sc. Computer Science", "CSC-BSC"),
    ("prog-mth", "dept-mth", "B.Sc. Mathematics", "MTH-BSC"),
    ("prog-phy", "dept-phy", "B.Sc. Physics", "PHY-BSC"),
    ("prog-eee", "dept-eee", "B.Eng. Electrical and Electronic Engineering", "EEE-BENG"),
)

LECTURERS = (
    ("lec-001", "dept-csc", "Dr Adaeze Okonkwo", ("csc-101", "csc-102")),
    ("lec-002", "dept-csc", "Dr Chinedu Alabi", ("csc-201", "csc-202", "csc-301")),
    ("lec-003", "dept-mth", "Prof Bola Ajayi", ("mth-101", "mth-102")),
    ("lec-004", "dept-mth", "Dr Yusuf Garba", ("mth-201", "mth-202")),
    ("lec-005", "dept-phy", "Dr Ifeoma Nnaji", ("phy-101", "phy-102", "phy-201")),
    ("lec-006", "dept-eee", "Engr Tayo Sobowale", ("eee-101", "eee-102", "eee-201")),
)


@dataclass(frozen=True)
class CourseFixture:
    course_id: str
    department_id: str
    code: str
    title: str
    credit_units: int
    prerequisite_ids: tuple[str, ...] = ()
    retired: bool = False


COURSES = (
    CourseFixture("csc-101", "dept-csc", "CSC101", "Introduction to Computer Science", 3),
    CourseFixture("csc-102", "dept-csc", "CSC102", "Introduction to Programming", 3),
    CourseFixture("csc-201", "dept-csc", "CSC201", "Data Structures", 3, ("csc-101",)),
    CourseFixture("csc-202", "dept-csc", "CSC202", "Computer Architecture", 3),
    CourseFixture("csc-301", "dept-csc", "CSC301", "Analysis of Algorithms", 3, ("csc-201",)),
    CourseFixture("csc-310", "dept-csc", "CSC310", "Pascal Programming", 2, retired=True),
    CourseFixture("mth-101", "dept-mth", "MTH101", "Elementary Mathematics I", 3),
    CourseFixture("mth-102", "dept-mth", "MTH102", "Elementary Mathematics II", 3),
    CourseFixture("mth-201", "dept-mth", "MTH201", "Linear Algebra", 3),
    CourseFixture("mth-202", "dept-mth", "MTH202", "Differential Equations", 3),
    CourseFixture("phy-101", "dept-phy", "PHY101", "General Physics I: Mechanics", 3),
    CourseFixture("phy-102", "dept-phy", "PHY102", "General Physics II: Electromagnetism", 3),
    CourseFixture("phy-201", "dept-phy", "PHY201", "Thermodynamics", 3),
    CourseFixture("eee-101", "dept-eee", "EEE101", "Basic Electrical Engineering", 4),
    CourseFixture("eee-102", "dept-eee", "EEE102", "Engineering Drawing", 2),
    CourseFixture("eee-201", "dept-eee", "EEE201", "Circuit Theory", 4, ("eee-101",)),
)

SESSION_FEE_LINES = ("prog-csc", "prog-mth", "prog-phy")
"""Which programs this session is priced for at level 100.

``prog-eee`` is deliberately absent. A combination the schedule does not price is *skipped
and reported* rather than raising (CLAUDE.md section 3), and leaving one gap here means the
seeded data actually exercises that branch: the Engineering account carries no session
charge, and its holder is therefore not financially cleared to register.
"""

ADMISSION_QUOTAS = {"prog-csc": 6, "prog-mth": 6, "prog-phy": 6, "prog-eee": 1}
"""``prog-eee`` is full once its single place is taken, so a new application to Engineering
demonstrates the alternative-offer path rather than the easy one."""

ENTRY_REQUIREMENTS = {
    "prog-csc": (("USE OF ENGLISH", "MATHEMATICS"), (("PHYSICS", "CHEMISTRY"),)),
    "prog-mth": (("USE OF ENGLISH", "MATHEMATICS"), (("PHYSICS", "ECONOMICS"),)),
    "prog-phy": (("USE OF ENGLISH", "MATHEMATICS", "PHYSICS"), (("CHEMISTRY", "BIOLOGY"),)),
    "prog-eee": (
        ("USE OF ENGLISH", "MATHEMATICS", "PHYSICS"),
        (("CHEMISTRY", "FURTHER MATHEMATICS"),),
    ),
}

ALTERNATIVE_POLICIES = {
    "prog-csc": ("prog-mth", "prog-phy"),
    "prog-eee": ("prog-phy",),
    "prog-mth": (),
    "prog-phy": (),
}

SCIENCE_SUBJECTS = ("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", "CHEMISTRY")

APPLIED = "applied"
SCREENED = "screened"
OFFERED = "offered"
DECLINED = "declined"
ACCEPTED = "accepted"
ACCEPTED_PAID = "accepted_paid"
MATRICULATED = "matriculated"
NO_OFFER = "no_offer"

HOLDS_A_PLACE = frozenset({OFFERED, DECLINED, ACCEPTED, ACCEPTED_PAID, MATRICULATED})
"""End states reached by claiming a place on a cycle. A declined offer is not given back —
nothing in the domain returns a place — so it still counts against the quota."""

HAS_AN_ACCOUNT = frozenset({ACCEPTED, ACCEPTED_PAID, MATRICULATED})
"""``OpenAccountForOffer`` is driven by ``OfferAccepted``, so accepting is what opens one."""


@dataclass(frozen=True)
class ApplicantFixture:
    """One applicant, and how far through the state machine they were driven.

    The email address and phone number are derived rather than listed: they are the two
    optional fields on ``BioData`` and what matters about them here is only that they are
    populated, so spelling fourteen of each out would be noise around the columns that do
    carry a decision.
    """

    applicant_id: str
    full_name: str
    date_of_birth: date
    applied_program_id: str
    end_state: str
    offered_program_id: str | None = None
    scores: tuple[int, ...] = (70, 75, 68, 62)
    subjects: tuple[str, ...] = SCIENCE_SUBJECTS

    @property
    def email(self) -> str:
        return f"{self.full_name.lower().replace(' ', '.')}@example.ng"

    @property
    def phone_number(self) -> str:
        return f"0801234{self.applicant_id.removeprefix('app-')}"

    @property
    def utme_result(self) -> UtmeResult:
        return UtmeResult(
            tuple(
                UtmeSubjectScore(subject=subject, score=score)
                for subject, score in zip(self.subjects, self.scores, strict=True)
            )
        )


# fmt: off
# Kept as a table on purpose: what each applicant demonstrates is legible across a row and
# invisible down a column of one argument per line.
APPLICANTS = (
    ApplicantFixture(
        "app-0001", "Adaeze Okonkwo", date(2008, 4, 17), "prog-csc", MATRICULATED, "prog-csc",
        (78, 82, 71, 69),
    ),
    ApplicantFixture(
        "app-0002", "Chidi Nwosu", date(2008, 1, 3), "prog-csc", MATRICULATED, "prog-csc",
        (64, 71, 60, 58),
    ),
    ApplicantFixture(
        "app-0003", "Halima Bello", date(2007, 11, 22), "prog-csc", MATRICULATED, "prog-csc",
        (72, 68, 66, 61),
    ),
    ApplicantFixture(
        "app-0004", "Emeka Obi", date(2008, 6, 9), "prog-mth", MATRICULATED, "prog-mth",
        (69, 88, 74, 60),
    ),
    # Applied for Computer Science, seated on Physics: the alternative-offer path, and the
    # reason `offered_program_id` is a second column rather than a correction of the first.
    ApplicantFixture(
        "app-0005", "Folake Adeyemi", date(2008, 2, 14), "prog-csc", MATRICULATED, "prog-phy",
        (61, 58, 70, 64),
    ),
    ApplicantFixture(
        "app-0006", "Ibrahim Sani", date(2007, 9, 30), "prog-eee", MATRICULATED, "prog-eee",
        (66, 79, 77, 65),
    ),
    ApplicantFixture(
        "app-0007", "Ngozi Eze", date(2008, 7, 25), "prog-csc", ACCEPTED, "prog-csc",
        (63, 65, 59, 57),
    ),
    ApplicantFixture(
        "app-0008", "Tunde Balogun", date(2008, 3, 12), "prog-csc", ACCEPTED_PAID, "prog-csc",
        (70, 67, 64, 60),
    ),
    ApplicantFixture(
        "app-0009", "Aisha Yusuf", date(2008, 5, 5), "prog-mth", OFFERED, "prog-mth",
        (68, 80, 62, 59),
    ),
    ApplicantFixture(
        "app-0010", "Kelechi Umeh", date(2007, 12, 1), "prog-eee", OFFERED, "prog-phy",
        (64, 72, 75, 63),
    ),
    ApplicantFixture(
        "app-0011", "Bisi Ogunleye", date(2008, 8, 19), "prog-phy", DECLINED, "prog-phy",
        (60, 66, 71, 58),
    ),
    ApplicantFixture(
        "app-0012", "Musa Danjuma", date(2008, 10, 7), "prog-csc", SCREENED,
        scores=(59, 62, 57, 55),
    ),
    ApplicantFixture(
        "app-0013", "Grace Etim", date(2008, 4, 2), "prog-eee", APPLIED,
        scores=(65, 70, 68, 61),
    ),
    # Engineering's one place is gone and Physics — its only alternative — demands Chemistry
    # or Biology, which this combination does not carry. Hence no offer available.
    ApplicantFixture(
        "app-0014", "Segun Alabi", date(2007, 10, 28), "prog-eee", NO_OFFER,
        scores=(62, 74, 70, 66),
        subjects=("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", "FURTHER MATHEMATICS"),
    ),
)
# fmt: on

STUDENT_IDS = {
    "app-0001": "stu-0001",
    "app-0002": "stu-0002",
    "app-0003": "stu-0003",
    "app-0004": "stu-0004",
    "app-0005": "stu-0005",
    "app-0006": "stu-0006",
}
"""Which matriculated applicant becomes which student. Issued in this order, so the matric
numbers run 260591001, 260591002, 260591003 for Computer Science and 001 for the rest.

**These ids belong to Student Profile and go no further.** Downstream — Enrollment, Academic
Records, Billing — a student is identified by their *matric number*: Billing keys one ledger
by a neutral party-id and links the matric number to it at matriculation (CLAUDE.md section
3, "party-id"), and ``BillingFinancialClearanceAdapter`` passes Enrollment's ``student_id``
across as that party-id with no translation. Seeding a registration under ``stu-0001`` would
therefore produce a student whom no ledger can be found for, and every one of them would read
as not financially cleared. The tables below are written in these ids because they are the
legible ones, and :func:`_seed_students` returns the mapping that converts them.
"""


@dataclass(frozen=True)
class PaymentFixture:
    gateway_ref: str
    amount: Money


PAYMENTS: dict[str, tuple[PaymentFixture, ...]] = {
    # Charges are 20,000 + 50,000 + 150,000 = 220,000. Allocation is gating charge first,
    # then in the order raised, so what lands on the *session* charge — the only figure
    # clearance reads — is what the two right-hand columns of this table come to.
    #
    #                                   paid       -> session fee     clearance
    # app-0001                          225,000       150,000 (100%)  both semesters
    # app-0002                          175,000       105,000  (70%)  first semester only
    # app-0003                           20,000             0         neither
    # app-0004                          220,000       150,000 (100%)  both semesters
    # app-0005                          175,000       105,000  (70%)  first semester only
    # app-0006                           70,000       no charge       neither (unpriced)
    # app-0007                                0             0         neither
    # app-0008                           20,000             0         neither
    "app-0001": (
        PaymentFixture("PSK-SEED-A001", Money("200000")),
        PaymentFixture("PSK-SEED-A002", Money("25000")),
    ),
    "app-0002": (PaymentFixture("PSK-SEED-B001", Money("175000")),),
    "app-0003": (PaymentFixture("PSK-SEED-C001", Money("20000")),),
    "app-0004": (PaymentFixture("PSK-SEED-D001", Money("220000")),),
    "app-0005": (PaymentFixture("PSK-SEED-E001", Money("175000")),),
    "app-0006": (PaymentFixture("PSK-SEED-F001", Money("70000")),),
    "app-0007": (),
    "app-0008": (PaymentFixture("PSK-SEED-H001", Money("20000")),),
}

OPEN_INTENT = ("PSK-SEED-G001", "app-0007", Money("20000"))
"""A checkout nobody finished. Older than the one-hour TTL, so the reconciliation sweep has
something to ask the gateway about."""

FAILED_INTENT = ("PSK-SEED-H002", "app-0008", Money("50000"), "card declined")

CLEARED_FOR_BOTH_SEMESTERS = ("stu-0001", "stu-0004")
CLEARED_FOR_FIRST_SEMESTER = ("stu-0002", "stu-0005")
"""Who the figures above clear, and the constraint the registrations below are written under.

Nothing reads these: they are the arithmetic stated in the ids the enrollment table uses, so
that a later edit to a payment can be checked against the registrations it would invalidate.
"""


@dataclass(frozen=True)
class OfferingFixture:
    course_id: str
    term: Term
    capacity: int


OFFERINGS = (
    OfferingFixture("csc-101", FIRST_TERM, 120),
    OfferingFixture("csc-102", FIRST_TERM, 100),
    OfferingFixture("csc-202", FIRST_TERM, 60),
    OfferingFixture("mth-101", FIRST_TERM, 120),
    OfferingFixture("mth-102", FIRST_TERM, 100),
    OfferingFixture("phy-101", FIRST_TERM, 120),
    OfferingFixture("phy-102", FIRST_TERM, 80),
    OfferingFixture("eee-101", FIRST_TERM, 60),
    OfferingFixture("eee-102", FIRST_TERM, 40),
    OfferingFixture("csc-101", SECOND_TERM, 60),
    OfferingFixture("csc-201", SECOND_TERM, 80),
    OfferingFixture("csc-301", SECOND_TERM, 60),
    OfferingFixture("mth-102", SECOND_TERM, 100),
    OfferingFixture("mth-201", SECOND_TERM, 80),
    OfferingFixture("mth-202", SECOND_TERM, 60),
    OfferingFixture("phy-102", SECOND_TERM, 80),
    OfferingFixture("phy-201", SECOND_TERM, 60),
    OfferingFixture("eee-201", SECOND_TERM, 40),
)

REGISTERED = "registered"
AWAITING_GRADE = "awaiting_grade"
FINALIZED = "finalized"


@dataclass(frozen=True)
class EnrollmentFixture:
    student_id: str
    course_id: str
    term: Term
    status: str
    is_carry_over: bool = False


ENROLLMENTS = (
    # First semester, graded and finalized. Twelve units each: the confirmed cap is 24.
    EnrollmentFixture("stu-0001", "csc-101", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0001", "csc-102", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0001", "mth-101", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0001", "phy-101", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0002", "csc-101", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0002", "csc-102", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0002", "mth-101", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0002", "phy-101", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0004", "mth-101", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0004", "mth-102", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0004", "csc-101", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0004", "phy-101", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0005", "phy-101", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0005", "phy-102", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0005", "mth-101", FIRST_TERM, FINALIZED),
    EnrollmentFixture("stu-0005", "csc-101", FIRST_TERM, FINALIZED),
    # Second semester, in progress. Only the two students cleared to 100% of the session fee
    # appear here: second-semester registration requires the whole of it.
    EnrollmentFixture("stu-0001", "csc-201", SECOND_TERM, AWAITING_GRADE),
    EnrollmentFixture("stu-0001", "mth-102", SECOND_TERM, REGISTERED),
    EnrollmentFixture("stu-0001", "phy-102", SECOND_TERM, REGISTERED),
    # A carry-over: csc-101 was failed in the first semester and is being sat again. Both
    # attempts stay on the transcript and both count towards the CGPA.
    EnrollmentFixture("stu-0004", "csc-101", SECOND_TERM, REGISTERED, is_carry_over=True),
    EnrollmentFixture("stu-0004", "mth-201", SECOND_TERM, REGISTERED),
)

GRADES = (
    # (student, course, semester, score). Spread across all five bands of the confirmed
    # scale: A 70-100, B 60-69, C 50-59, D 40-49, F 0-39.
    ("stu-0001", "csc-101", FIRST_SEMESTER_ID, 78),
    ("stu-0001", "csc-102", FIRST_SEMESTER_ID, 65),
    ("stu-0001", "mth-101", FIRST_SEMESTER_ID, 55),
    ("stu-0001", "phy-101", FIRST_SEMESTER_ID, 45),
    ("stu-0002", "csc-101", FIRST_SEMESTER_ID, 26),  # corrected to 62 below
    ("stu-0002", "csc-102", FIRST_SEMESTER_ID, 51),
    ("stu-0002", "mth-101", FIRST_SEMESTER_ID, 35),
    ("stu-0002", "phy-101", FIRST_SEMESTER_ID, 44),
    ("stu-0004", "mth-101", FIRST_SEMESTER_ID, 88),
    ("stu-0004", "mth-102", FIRST_SEMESTER_ID, 72),
    ("stu-0004", "csc-101", FIRST_SEMESTER_ID, 39),
    ("stu-0004", "phy-101", FIRST_SEMESTER_ID, 58),
    # Four failures and near-failures: CGPA 1.00, below the confirmed 1.50 threshold, so
    # this student reads as PROBATION.
    ("stu-0005", "phy-101", FIRST_SEMESTER_ID, 38),
    ("stu-0005", "phy-102", FIRST_SEMESTER_ID, 42),
    ("stu-0005", "mth-101", FIRST_SEMESTER_ID, 30),
    ("stu-0005", "csc-101", FIRST_SEMESTER_ID, 41),
)

CORRECTION = ("stu-0002", "csc-101", FIRST_SEMESTER_ID, 62, "marks transposed", "Registrar")
"""One administrative correction, so a ``GradeCorrection`` audit row exists in the data."""


# =========================================================================================
# The seeder
# =========================================================================================


@dataclass
class Summary:
    """What was written, and what was deliberately skipped."""

    counts: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def record(self, what: str, how_many: int) -> None:
        self.counts[what] = self.counts.get(what, 0) + how_many

    def note(self, message: str) -> None:
        self.notes.append(message)

    def render(self) -> str:
        width = max(len(what) for what in self.counts) if self.counts else 0
        lines = [f"  {what.ljust(width)}  {count:>4}" for what, count in self.counts.items()]
        if self.notes:
            lines.append("")
            lines.extend(f"  note: {note}" for note in self.notes)
        return "\n".join(lines)


async def seed_all(engine: AsyncEngine) -> Summary:
    """Write the whole demo university. The tables must already exist.

    Steps run in dependency order, and the order is forced by ids referenced across
    contexts: a student cannot be issued a matric number before the department code exists,
    an account cannot be priced before the fee schedule is published, and a transcript line
    cannot snapshot credit units before the course carries any.
    """
    summary = Summary()
    await _seed_faculty_department(engine, summary)
    await _seed_course_catalog(engine, summary)
    schedule = await _seed_fee_schedule(engine, summary)
    await _seed_admissions(engine, summary)
    issued = await _seed_students(engine, summary)
    # The one translation this script performs, and the reason it is here rather than inside
    # a step: three contexts identify a student by the matric number Student Profile issued,
    # and the fixture tables above are written in Student Profile's own ids.
    matric_of = {STUDENT_IDS[applicant_id]: number for applicant_id, number in issued.items()}
    await _seed_enrollment(engine, matric_of, summary)
    await _seed_academic_records(engine, matric_of, summary)
    await _seed_billing(engine, schedule, issued, summary)
    return summary


async def _seed_faculty_department(engine: AsyncEngine, summary: Summary) -> None:
    """Faculties, departments, programs, the session, and who teaches what."""
    faculties = PostgresFacultyRepository(engine)
    for faculty_id, name, code in FACULTIES:
        await faculties.add(Faculty(faculty_id, name, code))
    summary.record("faculties", len(FACULTIES))

    departments = PostgresDepartmentRepository(engine)
    for department_id, faculty_id, name, code in DEPARTMENTS:
        await departments.add(Department(department_id, faculty_id, name, code))
    summary.record("departments", len(DEPARTMENTS))

    programs = PostgresProgramRepository(engine)
    for program_id, department_id, name, code in PROGRAMS:
        program = Program.create(program_id, department_id, name, code)
        # `create` leaves a program closed deliberately, and Admissions checks the flag at
        # application time — so a seeded program nobody opened would refuse every applicant.
        program.open_admissions()
        await programs.add(program)
    summary.record("programs", len(PROGRAMS))

    session = Session.plan(
        SESSION_ID,
        AcademicYear(SESSION_START_YEAR),
        [
            Semester(FIRST_SEMESTER_ID, FacultySemesterOrdinal.FIRST),
            Semester(SECOND_SEMESTER_ID, FacultySemesterOrdinal.SECOND),
        ],
    )
    # `open()` returns SessionOpened and this script is not a composition root: it publishes
    # nothing, and writes the fee schedule and the charges that handler would have raised
    # directly instead.
    session.open()
    await PostgresSessionRepository(engine).add(session)
    summary.record("sessions", 1)

    lecturers = PostgresLecturerRepository(engine)
    for lecturer_id, department_id, name, course_ids in LECTURERS:
        lecturer = Lecturer(lecturer_id, department_id, name)
        for course_id in course_ids:
            # Assignments are session-scoped, which is what makes the grade-submission route
            # usable against seeded data: it authorizes on exactly this.
            lecturer.assign_to_course(course_id, SESSION_ID)
        await lecturers.add(lecturer)
    summary.record("lecturers", len(LECTURERS))


async def _seed_course_catalog(engine: AsyncEngine, summary: Summary) -> None:
    """The catalog, with one real prerequisite chain and one retired course."""
    courses = PostgresCourseRepository(engine)
    for fixture in COURSES:
        course = Course.create(
            fixture.course_id,
            fixture.department_id,
            fixture.code,
            fixture.title,
            fixture.credit_units,
        )
        for prerequisite_id in fixture.prerequisite_ids:
            course.add_prerequisite(prerequisite_id)
        if fixture.retired:
            # Retired rather than deleted: a transcript refers to courses no longer taught,
            # so an id that once resolved must keep resolving.
            course.retire()
        await courses.add(course)
    summary.record("courses", len(COURSES))


async def _seed_fee_schedule(engine: AsyncEngine, summary: Summary) -> FeeSchedule:
    """What this session costs. Published before any account, because accounts price off it."""
    schedule = FeeSchedule.for_session(
        SESSION_ID,
        acceptance_fee=ACCEPTANCE_FEE,
        matriculation_fee=MATRICULATION_FEE,
        session_fees=tuple(
            SessionFeeLine(
                program_id=program_id, level=BillingLevel(ENTRY_LEVEL), amount=SESSION_FEE
            )
            for program_id in SESSION_FEE_LINES
        ),
    )
    await PostgresFeeScheduleRepository(engine).add(schedule)
    summary.record("fee schedules", 1)
    return schedule


async def _seed_admissions(engine: AsyncEngine, summary: Summary) -> None:
    """Cycles, requirements, fallback chains, and applicants in every state of the machine."""
    cycles = PostgresAdmissionCycleRepository(engine)
    open_cycles = {
        program_id: AdmissionCycle.open(program_id, SESSION_ID, quota)
        for program_id, quota in ADMISSION_QUOTAS.items()
    }
    for cycle in open_cycles.values():
        await cycles.add(cycle)
    summary.record("admission cycles", len(open_cycles))

    requirements = PostgresProgramEntryRequirementRepository(engine)
    for program_id, (required, groups) in ENTRY_REQUIREMENTS.items():
        await requirements.add(
            ProgramEntryRequirement.for_program(
                program_id,
                SESSION_ID,
                required_subjects=required,
                one_of_groups=[SubjectGroup(options=frozenset(group)) for group in groups],
            )
        )
    summary.record("entry requirements", len(ENTRY_REQUIREMENTS))

    policies = PostgresAlternativeProgramPolicyRepository(engine)
    for program_id, alternatives in ALTERNATIVE_POLICIES.items():
        await policies.add(
            AlternativeProgramPolicy.for_program(program_id, SESSION_ID, alternatives)
        )
    summary.record("alternative policies", len(ALTERNATIVE_POLICIES))

    applicants = PostgresApplicantRepository(engine)
    for fixture in APPLICANTS:
        applicant = Applicant.apply(
            fixture.applicant_id,
            fixture.applied_program_id,
            SESSION_ID,
            BioData(
                full_name=fixture.full_name,
                date_of_birth=fixture.date_of_birth,
                email=fixture.email,
                phone_number=fixture.phone_number,
            ),
            fixture.utme_result,
        )
        if fixture.end_state in HOLDS_A_PLACE:
            # The place is claimed on the cycle and saved before the applicant records that
            # they hold it — the ordering MakeOfferToApplicant uses, so a crash between the
            # two under-admits rather than over-admits.
            cycle = open_cycles[fixture.offered_program_id]
            cycle.offer()
            await cycles.save(cycle)
        _drive_to(applicant, fixture)
        await applicants.add(applicant)
    summary.record("applicants", len(APPLICANTS))


def _drive_to(applicant: Applicant, fixture: ApplicantFixture) -> None:
    """Walk an applicant through real transitions to the state the fixture asks for.

    Never ``restore``: that classmethod belongs to persistence adapters, and a seeder that
    used it could write a combination no sequence of transitions produces.
    """
    if fixture.end_state == APPLIED:
        return
    applicant.screen()
    if fixture.end_state == SCREENED:
        return
    if fixture.end_state == NO_OFFER:
        applicant.record_no_offer()
        return
    applicant.offer(fixture.offered_program_id)
    if fixture.end_state == OFFERED:
        return
    if fixture.end_state == DECLINED:
        applicant.decline()
        return
    applicant.accept()
    if fixture.end_state == ACCEPTED:
        return
    applicant.record_acceptance_fee_paid()
    if fixture.end_state == ACCEPTED_PAID:
        return
    applicant.matriculate()


async def _seed_students(engine: AsyncEngine, summary: Summary) -> dict[str, str]:
    """Turn the matriculated applicants into students, through the real issuer.

    Returns the applicant id -> matric number mapping, which Billing needs to link each
    ledger to the number its holder was issued.
    """
    department_of_program = {
        program_id: department_id for program_id, department_id, _, _ in PROGRAMS
    }
    numeric_code_of_department = {
        department_id: DEPARTMENT_NUMERIC_CODES[code] for department_id, _, _, code in DEPARTMENTS
    }

    students = PostgresStudentRepository(engine)
    sequences = PostgresMatricSequenceRepository(engine)
    issuer = MatricNumberIssuer()
    issued: dict[str, str] = {}
    counters: set[str] = set()

    for fixture in APPLICANTS:
        if fixture.end_state != MATRICULATED:
            continue
        program_id = fixture.offered_program_id
        numeric_code = numeric_code_of_department[department_of_program[program_id]]

        counters.add(numeric_code)
        sequence = await sequences.get_or_start(
            DepartmentCode(numeric_code), EntryYear(SESSION_START_YEAR)
        )
        matric_number = issuer.issue(sequence)
        # The sequence is saved *before* the student who used the number, so a crash between
        # the two burns a number rather than leaving a live student whose number will be
        # handed out again. The port says so; this is the caller obeying it.
        await sequences.save(sequence)

        await students.add(
            Student(
                STUDENT_IDS[fixture.applicant_id],
                matric_number,
                StudentBioData(
                    full_name=fixture.full_name,
                    date_of_birth=fixture.date_of_birth,
                    email=fixture.email,
                    phone_number=fixture.phone_number,
                ),
                program_id,
                SESSION_ID,
                StudentLevel(ENTRY_LEVEL),
                applicant_id=fixture.applicant_id,
            )
        )
        issued[fixture.applicant_id] = matric_number.value

    summary.record("students", len(issued))
    summary.record("matric sequences", len(counters))
    return issued


async def _seed_enrollment(
    engine: AsyncEngine, matric_of: dict[str, str], summary: Summary
) -> None:
    """Offerings, then registrations against them — one claimed seat per registration.

    Registrations are keyed by matric number, because that is what Enrollment hands Billing
    as a party-id when it asks whether a student is financially cleared. See ``STUDENT_IDS``.
    """
    credit_units = {fixture.course_id: fixture.credit_units for fixture in COURSES}
    prerequisites = {fixture.course_id: fixture.prerequisite_ids for fixture in COURSES}

    offerings = PostgresCourseOfferingRepository(engine)
    open_offerings: dict[tuple[str, Term], CourseOffering] = {}
    for fixture in OFFERINGS:
        offering = CourseOffering.open(fixture.course_id, fixture.term, fixture.capacity)
        await offerings.add(offering)
        open_offerings[(fixture.course_id, fixture.term)] = offering
    summary.record("course offerings", len(OFFERINGS))

    enrollments = PostgresEnrollmentRepository(engine)
    for index, fixture in enumerate(ENROLLMENTS, start=1):
        offering = open_offerings[(fixture.course_id, fixture.term)]
        # Claim the seat and save the offering first: an enrollment written without one
        # leaves `seats_taken` lying about a register that has students in it.
        outcome = offering.claim_seat()
        if not isinstance(outcome, SeatClaimed):
            raise RuntimeError(
                f"the seeded offering of {fixture.course_id} in {fixture.term} is full; "
                "its capacity is too small for the registrations this script writes"
            )
        await offerings.save(offering)

        enrollment = Enrollment.register(
            f"enr-{index:04d}",
            matric_of[fixture.student_id],
            CourseFacts(
                fixture.course_id,
                credit_units[fixture.course_id],
                prerequisite_ids=prerequisites[fixture.course_id],
            ),
            fixture.term,
            is_carry_over=fixture.is_carry_over,
        )
        if fixture.status in (AWAITING_GRADE, FINALIZED):
            enrollment.await_grade()
        if fixture.status == FINALIZED:
            enrollment.finalize()
        await enrollments.add(enrollment)
    summary.record("enrollments", len(ENROLLMENTS))


async def _seed_academic_records(
    engine: AsyncEngine, matric_of: dict[str, str], summary: Summary
) -> None:
    """Transcripts, from the same grades the finalized enrollments were graded on.

    Keyed by matric number for the same reason registrations are: Enrollment reads a standing
    back out of here through ``StudentAcademicStandingPort``, under the id it was given.
    """
    credit_units = {fixture.course_id: fixture.credit_units for fixture in COURSES}

    records = PostgresAcademicRecordRepository(engine)
    open_records: dict[str, AcademicRecord] = {}
    for student, course_id, semester_id, score in GRADES:
        student_id = matric_of[student]
        record = open_records.get(student_id)
        if record is None:
            record = AcademicRecord.open(student_id)
            open_records[student_id] = record
        # The units snapshotted here are the ones the enrollment snapshotted, which is what
        # makes a transcript and a registration agree about what a course was worth.
        record.record_grade(
            course_id=course_id,
            semester_id=semester_id,
            score=score,
            credit_units=credit_units[course_id],
        )
    for record in open_records.values():
        await records.add(record)

    student, course_id, semester_id, corrected, reason, authorizer = CORRECTION
    corrected_record = open_records[matric_of[student]]
    corrected_record.correct_grade(
        course_id=course_id,
        semester_id=semester_id,
        corrected_score=corrected,
        reason=reason,
        authorized_by=authorizer,
    )
    await records.save(corrected_record)

    summary.record("academic records", len(open_records))
    summary.record("grades", len(GRADES))
    summary.record("grade corrections", 1)


async def _seed_billing(
    engine: AsyncEngine, schedule: FeeSchedule, students: dict[str, str], summary: Summary
) -> None:
    """Ledgers, in the order the two event handlers would have raised them.

    Acceptance fee, then matriculation fee — both from ``OfferAccepted`` — then the session
    fee that ``SessionOpened`` batch-applies. The order is not cosmetic: allocation is
    gating-charge-first and then in the order raised, so writing them in a different order
    would put somebody's money against a different charge.
    """
    accounts = PostgresAccountRepository(engine)
    intents = PostgresPaymentIntentRepository(engine)
    written = 0
    payments = 0

    for fixture in APPLICANTS:
        if fixture.end_state not in HAS_AN_ACCOUNT:
            continue
        program_id = fixture.offered_program_id
        account = Account.open(fixture.applicant_id, program_id)
        account.raise_acceptance_fee(SESSION_ID, schedule.acceptance_fee)
        account.raise_matriculation_fee(SESSION_ID, schedule.matriculation_fee)

        session_fee = schedule.session_fee_for(program_id, BillingLevel(ENTRY_LEVEL))
        if session_fee is None:
            # Skipped and reported, exactly as ApplySessionFees does: a program the schedule
            # does not price is one nobody has priced yet, and refusing would stop the whole
            # cohort being charged over one gap. The visible consequence is that this party
            # is not financially cleared to register, because there is no session charge
            # against which 70% can be shown to have been paid.
            summary.note(
                f"{fixture.applicant_id}: no session fee on the schedule for {program_id} "
                f"at level {ENTRY_LEVEL}; charge skipped, and this party is not cleared"
            )
        else:
            account.raise_session_fee(SESSION_ID, session_fee)

        matric_number = students.get(fixture.applicant_id)
        if matric_number is not None:
            account.link_student_id(matric_number)

        for payment in PAYMENTS.get(fixture.applicant_id, ()):
            # The intent's reference *is* the gateway ref on the ledger. One key across both
            # aggregates is what makes the whole path idempotent without a dedupe table.
            intent = PaymentIntent.initiate(
                payment.gateway_ref, fixture.applicant_id, payment.amount, initiated_at=PAID_AT
            )
            intent.confirm(amount=payment.amount, at=PAID_AT)
            await intents.add(intent)
            account.apply_payment(
                gateway_ref=payment.gateway_ref, amount=payment.amount, received_at=PAID_AT
            )
            payments += 1

        await accounts.add(account)
        written += 1

    reference, party_id, amount = OPEN_INTENT
    await intents.add(PaymentIntent.initiate(reference, party_id, amount, initiated_at=PAID_AT))
    reference, party_id, amount, reason = FAILED_INTENT
    failed = PaymentIntent.initiate(reference, party_id, amount, initiated_at=PAID_AT)
    failed.fail(reason, at=PAID_AT)
    await intents.add(failed)

    summary.record("billing accounts", written)
    summary.record("payments", payments)
    summary.record("payment intents", payments + 2)


# =========================================================================================
# The command line
# =========================================================================================


async def create_schema(engine: AsyncEngine) -> None:
    """Create the seven schemas and their tables, in ``tests/conftest.py``'s exact shape.

    A seeder that assumed the tables existed would be unusable on a fresh ``docker compose
    up -d db``, which is the only database most developers here will ever point it at. This
    is not a migration: see the module docstring.
    """
    async with engine.begin() as conn:
        for metadata in ALL_METADATA:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{metadata.schema}"'))
        for metadata in ALL_METADATA:
            await conn.run_sync(metadata.create_all)


def _all_table_names() -> Sequence[str]:
    return [
        f'"{metadata.schema}"."{table.name}"'
        for metadata in ALL_METADATA
        for table in metadata.sorted_tables
    ]


async def reset(engine: AsyncEngine) -> None:
    """Empty every table in one statement.

    ``RESTART IDENTITY`` matters more than it looks: the ``ordinal`` columns are what "in
    the order it was added" means, and a re-seed that left them running on from the last one
    would order faculties and semesters by an accident of history.
    """
    tables = ", ".join(_all_table_names())
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


async def is_populated(engine: AsyncEngine) -> bool:
    """Whether anything has already been seeded, asked of one table rather than all of them."""
    faculties = faculty_department_postgres.metadata.tables["faculty_department.faculties"]
    async with engine.connect() as conn:
        count = await conn.scalar(select(func.count()).select_from(faculties))
    return bool(count)


async def _run(database_url: str, *, wipe: bool) -> int:
    engine = engine_for(database_url)
    try:
        await create_schema(engine)
        if wipe:
            await reset(engine)
        elif await is_populated(engine):
            print(
                f"{database_url} already holds seeded data.\n"
                "Re-run with --reset to empty every table first.",
                file=sys.stderr,
            )
            return 1
        summary = await seed_all(engine)
    finally:
        await engine.dispose()

    print(f"seeded {database_url}\n")
    print(summary.render())
    print(
        "\nThe API needs the numeric department-code register to issue matric numbers.\n"
        "It has no default, deliberately (CLAUDE.md section 6). Put this in backend/.env:\n\n"
        f"  DEPARTMENT_NUMERIC_CODES={json.dumps(DEPARTMENT_NUMERIC_CODES, separators=(',', ':'))}"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="seed",
        description="Seed a development database with a coherent demo university.",
        epilog="Every value it writes is an invented demo fixture, not an institutional fact.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="empty every table before seeding. Off by default: this destroys data.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help=(
            "the database to seed. Defaults to $DATABASE_URL, then to "
            f"{DEFAULT_DATABASE_URL} — what `docker compose up -d db` gives you."
        ),
    )
    arguments = parser.parse_args(argv)
    database_url = arguments.database_url or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL
    return asyncio.run(_run(database_url, wipe=arguments.reset))


if __name__ == "__main__":
    raise SystemExit(main())
