"""
Shared fixtures for all backend tests.

Requires a test PostgreSQL database. Create it once:
    CREATE DATABASE university_db_test;

The test suite creates all tables on session start and drops them on session end.
Each test gets a fresh DB session that is rolled back after the test.
"""
import pytest
from httpx import AsyncClient, ASGITransport
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
# Session-scoped: create / drop tables once per test run
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Function-scoped DB session — rolls back after every test
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    async with TestSession() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# HTTP client wired to the test DB
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
# Helper: create a user directly in DB
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
    return create_access_token({"sub": str(user.id), "role": user.role, "username": user.username})


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
# Academic structure fixtures (function-scoped — created fresh each test)
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
        GradeScale(min_score=60, max_score=69, grade="B", grade_points=4.0, passed=True),
        GradeScale(min_score=50, max_score=59, grade="C", grade_points=3.0, passed=True),
        GradeScale(min_score=45, max_score=49, grade="D", grade_points=2.0, passed=True),
        GradeScale(min_score=0,  max_score=44, grade="F", grade_points=0.0, passed=False),
    ]
    for scale in scales:
        db.add(scale)
    await db.commit()
    return scales
