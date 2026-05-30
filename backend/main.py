from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.models import exam  # noqa: F401 — registers ExamSlot with Base metadata
from app.routers import (
    auth, users, students, staff, academic, courses,
    enrollment, attendance, assignments, grades,
    exams, payments, hostel, library, thesis,
    admission, notifications, reports,
)
from app.websockets.chat import router as chat_ws_router
from app.websockets.notifications import router as notifications_ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="University Management System API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,          prefix="/api/v1/auth",          tags=["Auth"])
app.include_router(users.router,         prefix="/api/v1/users",         tags=["Users"])
app.include_router(students.router,      prefix="/api/v1/students",      tags=["Students"])
app.include_router(staff.router,         prefix="/api/v1/staff",         tags=["Staff"])
app.include_router(academic.router,      prefix="/api/v1/academic",      tags=["Academic Structure"])
app.include_router(courses.router,       prefix="/api/v1/courses",       tags=["Courses"])
app.include_router(enrollment.router,    prefix="/api/v1/enrollment",    tags=["Enrollment"])
app.include_router(attendance.router,    prefix="/api/v1/attendance",    tags=["Attendance"])
app.include_router(assignments.router,   prefix="/api/v1/assignments",   tags=["Assignments"])
app.include_router(grades.router,        prefix="/api/v1/grades",        tags=["Grades"])
app.include_router(exams.router,         prefix="/api/v1/exams",         tags=["Exams"])
app.include_router(payments.router,      prefix="/api/v1/payments",      tags=["Payments"])
app.include_router(hostel.router,        prefix="/api/v1/hostel",        tags=["Hostel"])
app.include_router(library.router,       prefix="/api/v1/library",       tags=["Library"])
app.include_router(thesis.router,        prefix="/api/v1/thesis",        tags=["Thesis"])
app.include_router(admission.router,     prefix="/api/v1/admission",     tags=["Admission"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(reports.router,       prefix="/api/v1/reports",       tags=["Reports"])

app.include_router(chat_ws_router,           prefix="/ws")
app.include_router(notifications_ws_router,  prefix="/ws")
