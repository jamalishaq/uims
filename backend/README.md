# University Management System — API

FastAPI backend for the University Management System: seven bounded contexts behind one
hexagonal HTTP surface. See `CLAUDE.md` for the architecture and `UMS_BUILD_PLAYBOOK.md` for
how it was built, phase by phase.

> **This API has no authentication.** Routes that record payments, correct transcripts and
> sweep payment intents are reachable by anyone who can reach the process. Do not expose it to
> an untrusted network until an auth phase lands.

## Requirements

- Python 3.12+
- PostgreSQL 16 (`docker compose up -d db` gives you one)
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
cd backend
uv sync
cp .env.example .env
```

`src/main.py` is the only module that reads the environment. It requires `DATABASE_URL` and
`PAYSTACK_SECRET_KEY`, and fails at startup with their names if either is missing rather than
at the first request that needs them.

`DEPARTMENT_NUMERIC_CODES` deserves a note: it maps Faculty & Department's alphabetic
department code to the four digits a matric number carries, and it has **no default**. Nothing
in this repository states a real one, and a guess would be baked into every student number ever
issued. A department missing from the register cannot have students registered against it.

## Run

```bash
uv run uvicorn main:app --reload            # development
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4   # production
```

- Swagger UI: <http://localhost:8000/docs>
- OpenAPI schema: <http://localhost:8000/openapi.json>
- Liveness probe: `GET /health` — deliberately does not touch the database, so a blip the
  retry policy is about to ride out does not take the API out of rotation.

Every route is mounted under `/api/v1`, one router per context.

## Database

There are no migrations yet. The schema is created by the test fixtures and by the seeder
below; a deployment needs `alembic` set up first, which is why startup deliberately does *not*
run `create_all` — a process that built its own schema would make a half-migrated database
look healthy.

## Seed data

```bash
docker compose up -d db
uv run python scripts/seed.py --reset
```

`scripts/seed.py` writes one small demo university across all seven contexts — faculties,
courses, a session, applicants in every state of the admissions machine, students with real
matric numbers, registrations, transcripts and ledgers — so the read routes have something to
return. It writes through aggregates and repositories, never raw SQL, and it prints the
`DEPARTMENT_NUMERIC_CODES` line to put in `.env`.

Two things to know before relying on it:

- **Every value it writes is an invented demo fixture**, not an institutional fact. Fee
  amounts, quotas, entry requirements and three of the four numeric department codes were made
  up for the script and are marked as such in it. `CSC → 0591` is the one real entry.
- **`--reset` truncates every table**, and so does the Postgres test suite's `clean_database`
  fixture. Running `UMS_TEST_BACKEND=postgres uv run pytest` empties the database the seeder
  filled; re-seed afterwards.

It lives outside `src/` on purpose: a module that touches all seven contexts would violate rule
(b) of the fitness test, which exempts `src/main.py` alone and by exact name.

## Tests

```bash
uv run pytest                               # in-memory, needs no database
docker compose up -d db
UMS_TEST_BACKEND=postgres uv run pytest      # the same tests, against Postgres
uv run ruff check && uv run ruff format --check
```

`tests/architecture/test_dependency_rule.py` is the merge gate: four static rules over the
import graph. Red means stop.
