# University Management System

A full-stack web application for managing university operations — admissions, academics, finance, and more — with role-based access control across ten user roles.

## Features

- **Admissions** — Online applications, screening decisions, provisional offer letters
- **Academic Structure** — Faculties, departments, programs (BSc/MSc/PhD/PGDE), sessions, semesters
- **Course Management** — Sections, enrollment caps, prerequisites, credit hours
- **Course Registration** — Per-semester registration (15–21 credit load), add/drop, receipts
- **Attendance** — Lecturer marking, 75% enforcement, student dashboards
- **Assignments & Assessments** — Create, submit, and grade CA assessments
- **Exams** — Timetable, venue assignment, invigilation, result entry
- **Grades & GPA** — Multi-stage approval workflow (Lecturer → HOD → Dean → Registrar), carryover, CGPA
- **Transcripts** — Official PDF generation, clearance checklist, graduation audit
- **Finance** — Tuition/hostel/library fees, Paystack payments, partial payments, scholarships
- **Hostel** — Block/floor/room management, applications, allocation, waitlists
- **Library** — Catalog, borrowing, returns, overdue fines, clearance
- **Thesis & Dissertation** — Topic registration, supervision, progress reports, defense scheduling
- **Staff Management** — Staff profiles and directory
- **Notifications** — Real-time WebSocket feeds, course group chat, email tasks, notice board
- **Reports & Analytics** — Enrollment stats, pass/fail rates, fee collection, CGPA distribution
- **Alumni Portal** — Transcript download, verification letters

## User Roles

| Role | Responsibilities |
|------|-----------------|
| `super_admin` | Full system access, admin account management |
| `registrar` | Academic records, admissions, enrollment oversight |
| `bursar` | Fees, payments, financial reports |
| `dean` | Faculty-wide operations, result ratification |
| `hod` | Department operations, result approval |
| `lecturer` | Courses, attendance, grades, assignments |
| `student` | Course registration, attendance view, grades, payments |
| `applicant` | Apply, pay application fee, track admission status |
| `librarian` | Library catalog and borrowing management |
| `alumni` | Transcript download, verification letters |

## Tech Stack

**Frontend**
- React 18 + Vite
- React Router v6
- TanStack Query v5 (server state), Zustand (auth/theme)
- Axios with JWT interceptor + automatic token refresh
- React Hook Form + Zod
- Tailwind CSS, Lucide React, Recharts
- React Paystack, React Dropzone

**Backend**
- FastAPI (Python 3.11+) + Uvicorn
- PostgreSQL + SQLAlchemy 2.0 (async) + asyncpg
- Alembic (migrations)
- PyJWT + bcrypt (auth)
- Celery + Redis (async tasks: email, PDF generation)
- WebSockets with Redis Pub/Sub (multi-worker scalable)
- Paystack API, WeasyPrint (PDF), Pydantic v2

## Project Structure

```
sms/
├── backend/          # FastAPI REST + WebSocket API
│   ├── main.py       # App entry point, routers registered here
│   ├── app/
│   │   ├── core/     # Config, database, dependencies, security
│   │   ├── models/   # SQLAlchemy ORM models
│   │   ├── schemas/  # Pydantic DTOs
│   │   ├── routers/  # Route handlers (19 modules)
│   │   ├── services/ # Business logic
│   │   ├── tasks/    # Celery async tasks
│   │   └── websockets/ # Chat + notification handlers
│   ├── alembic/      # Database migrations
│   └── tests/
└── frontend/         # React 18 + Vite SPA
    └── src/
        ├── features/ # Domain modules (19 areas, each with queries + UI)
        ├── pages/    # Role-scoped page components
        ├── components/ # Shared UI components
        ├── store/    # Zustand stores (auth, theme)
        ├── hooks/    # useAuth, useTitle
        └── lib/      # Axios instance, TanStack Query client
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis

### Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY, REDIS_URL, Paystack keys, email credentials

# Run database migrations
alembic upgrade head

# Start API server (http://localhost:8000)
uvicorn main:app --reload

# Start Celery worker (separate terminal, for email/PDF tasks)
celery -A app.tasks.celery_app.celery worker --loglevel=info -Q email
```

API docs available at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env — set VITE_API_BASE_URL, VITE_WS_BASE_URL, VITE_PAYSTACK_PUBLIC_KEY

# Start dev server (http://localhost:5173)
npm run dev

# Run tests
npm test

# Production build
npm run build
```

## Environment Variables

### Backend (`backend/.env`)

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/university_db
SECRET_KEY=your-long-random-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
ALLOWED_ORIGINS=["http://localhost:5173"]
REDIS_URL=redis://localhost:6379/0
PAYSTACK_SECRET_KEY=sk_test_xxxxx
PAYSTACK_PUBLIC_KEY=pk_test_xxxxx
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USERNAME=your@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_FROM=noreply@university.edu.ng

# One-time superuser seed (remove after first run)
ADMIN_EMAIL=admin@university.edu.ng
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure-password
```

### Frontend (`frontend/.env`)

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_BASE_URL=ws://localhost:8000/ws
VITE_PAYSTACK_PUBLIC_KEY=pk_test_xxxxx
```

## API Overview

Base URL: `http://localhost:8000/api/v1`

Authentication uses Bearer JWT tokens. The frontend Axios instance attaches the token automatically and refreshes it on 401 responses using an httpOnly refresh cookie.

| Prefix | Domain |
|--------|--------|
| `/auth` | Login, token refresh, logout |
| `/users` | User management |
| `/students`, `/staff` | People records |
| `/academic` | Faculties, departments, programs, sessions |
| `/courses`, `/enrollment` | Course catalogue and registration |
| `/attendance`, `/assignments`, `/grades` | Academic activity |
| `/exams` | Timetable and results |
| `/payments` | Paystack integration and receipts |
| `/hostel`, `/library`, `/thesis` | Support services |
| `/admission` | Application lifecycle |
| `/notifications`, `/reports` | Communication and analytics |

WebSocket endpoints:
- `ws://localhost:8000/ws/chat/{section_id}?token=<JWT>` — Course group chat
- `ws://localhost:8000/ws/notifications?token=<JWT>` — Real-time notification feed

> WebSocket endpoints require a persistent server (e.g. Railway, Render, Fly.io) and cannot run on serverless platforms like Vercel.

## Database Migrations

```bash
# After changing a model, generate a new migration
alembic revision --autogenerate -m "describe the change"

# Apply pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1
```
