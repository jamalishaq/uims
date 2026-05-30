# University Management System — API

FastAPI backend for the University Management System.

## Requirements

- Python 3.11+
- PostgreSQL
- Redis

## Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and fill in your values:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/university_db
SECRET_KEY=your-random-secret-key
REDIS_URL=redis://localhost:6379/0
PAYSTACK_SECRET_KEY=sk_live_...
PAYSTACK_PUBLIC_KEY=pk_live_...
EMAIL_HOST=smtp.gmail.com
EMAIL_USERNAME=your@email.com
EMAIL_PASSWORD=your-app-password
EMAIL_FROM=noreply@university.edu.ng
```

## Database

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

## Run

```bash
# Development
uvicorn main:app --reload

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

API docs available at `http://localhost:8000/docs`

## Background Workers

In a separate terminal:

```bash
celery -A app.tasks.celery_app.celery worker --loglevel=info -Q email
```

## WebSocket Endpoints

| Endpoint | Description |
|---|---|
| `ws://localhost:8000/ws/chat/{section_id}?token=<jwt>` | Course group chat |
| `ws://localhost:8000/ws/notifications?token=<jwt>` | Real-time notifications |

Token is the JWT access token obtained from `/api/v1/auth/login`.
