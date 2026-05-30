"""
Shared fixtures for all backend tests.

Requires a test PostgreSQL database. Create it once with:
    CREATE DATABASE university_db_test;

Strategy:
- setup_database (session, sync): creates tables once with asyncio.run()
- db (function, async): fresh AsyncSession per test
- clean_tables (function, async, autouse): truncates all tables after every test
- client (function, async): AsyncClient wired to test db
"""
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from main import app
from app.core.database import Base, get_db
from app.core.security import hash_password, create_access_token
from app.models.user import User, UserRole
from app.models.academic import Faculty, Department, Program, DegreeType
from app.models.calendar import AcademicSession, Semester, SemesterName
from app.models.student import Student, StudentStatus
from app.models.course import Course, CourseSection, CourseType
from app.models.grade import GradeScale

import os
from datetime import date

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:oyinkan1@localhost:5432/university_db_test",
)

engine = create_async_engine(TEST_DB_URL, poolclass=NullPool, echo=False)
TestSession = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ---------------------------------------------------------------------------
# Session-scoped SYNC fixture — creates/drops tables once per run.
# Using asyncio.run() avoids event-loop scope conflicts with async fixtures.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def _drop():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_drop())


# ---------------------------------------------------------------------------
# Function-scoped async session
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    async with TestSession() as session:
        yield session


# ---------------------------------------------------------------------------
# Autouse: truncate all tables after each test (fast, avoids ordering issues)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def clean_tables():
    yield
    async with TestSession() as session:
        table_names = ", ".join(
            f'"{t.name}"' for t in Base.metadata.sorted_tables
        )
        await session.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
        await session.commit()


# ---------------------------------------------------------------------------
# HTTP client wired to the test DB session
# ---------------------------------------------------------------------------

@pytest.fixture
async def client(db: AsyncSession):
    async def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers (importable by test files)
# ---------------------------------------------------------------------------

async def make_user(db: AsyncSession, email: str, username: str, role: UserRole) -> User:
    user = User(
        email=email,
        username=username,
        password_hash=hash_password("Password123!"),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def token_for(user: User) -> str:
    return create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "username": user.username,
    })


def auth(user: User) -> dict:
    return {"Authorization": f"Bearer {token_for(user)}"}


# ---------------------------------------------------------------------------
# Role fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def admin(db):
    return await make_user(db, "admin@test.edu", "admin", UserRole.SUPER_ADMIN)

@pytest.fixture
async def registrar(db):
    return await make_user(db, "registrar@test.edu", "registrar", UserRole.REGISTRAR)

@pytest.fixture
async def bursar(db):
    return await make_user(db, "bursar@test.edu", "bursar", UserRole.BURSAR)

@pytest.fixture
async def lecturer(db):
    return await make_user(db, "lecturer@test.edu", "lecturer", UserRole.LECTURER)

@pytest.fixture
async def hod_user(db):
    return await make_user(db, "hod@test.edu", "hod", UserRole.HOD)

@pytest.fixture
async def applicant(db):
    return await make_user(db, "applicant@test.edu", "applicant", UserRole.APPLICANT)

@pytest.fixture
async def student_user(db):
    return await make_user(db, "student@test.edu", "student_user", UserRole.STUDENT)


# ---------------------------------------------------------------------------
# Academic structure fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def faculty(db):
    f = Faculty(name="Faculty of Science", code="SCI")
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return f

@pytest.fixture
async def department(db, faculty):
    d = Department(name="Computer Science", code="CSC", faculty_id=faculty.id)
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d

@pytest.fixture
async def program(db, department):
    p = Program(
        name="B.Sc Computer Science",
        code="BSCCSC",
        department_id=department.id,
        degree_type=DegreeType.BSC,
        duration_years=4,
        total_credits_required=120,
        core_credits_required=90,
        elective_credits_required=30,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p

@pytest.fixture
async def session(db):
    s = AcademicSession(
        name="2025/2026",
        start_date=date(2025, 9, 1),
        end_date=date(2026, 6, 30),
        is_current=True,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s

@pytest.fixture
async def semester(db, session):
    sem = Semester(
        session_id=session.id,
        name=SemesterName.FIRST,
        start_date=date(2025, 9, 1),
        end_date=date(2026, 1, 31),
        registration_start=date(2025, 8, 15),
        registration_end=date(2025, 9, 15),
        is_current=True,
    )
    db.add(sem)
    await db.commit()
    await db.refresh(sem)
    return sem

@pytest.fixture
async def course(db, department):
    c = Course(
        code="CSC101",
        title="Introduction to Programming",
        credit_hours=3,
        course_type=CourseType.CORE,
        department_id=department.id,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c

@pytest.fixture
async def section(db, course, semester, lecturer):
    s = CourseSection(
        course_id=course.id,
        semester_id=semester.id,
        lecturer_id=lecturer.id,
        max_enrollment=50,
        venue="LT1",
        schedule="Mon/Wed 08:00-09:30",
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s

@pytest.fixture
async def student(db, student_user, program):
    s = Student(
        user_id=student_user.id,
        matric_number="BSCCSC-2025-0001",
        program_id=program.id,
        level=100,
        status=StudentStatus.ACTIVE,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s

@pytest.fixture
async def grade_scale(db):
    scales = [
        GradeScale(min_score=70, max_score=100, grade="A", grade_points=5.0, passed=True),
        GradeScale(min_score=60, max_score=69,  grade="B", grade_points=4.0, passed=True),
        GradeScale(min_score=50, max_score=59,  grade="C", grade_points=3.0, passed=True),
        GradeScale(min_score=45, max_score=49,  grade="D", grade_points=2.0, passed=True),
        GradeScale(min_score=0,  max_score=44,  grade="F", grade_points=0.0, passed=False),
    ]
    for scale in scales:
        db.add(scale)
    await db.commit()
    return scales
