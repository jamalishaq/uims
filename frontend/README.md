# Frontend — University Management System

React 18 + Vite + TanStack Query + Zustand + Tailwind CSS.

**The rule this app is now built to: every page has an API route behind it.** The version this
replaces had seven whole feature areas — attendance, assignments, exams, hostel, library, thesis
and an alumni portal — with no backend at all, and nine roles the server has never issued a token
for. If you are adding a page, find the route first.

---

## Requirements

- Node.js 18+
- npm 9+

Or Docker, and none of the above: `docker compose up` at the repository root runs this app, the
API and Postgres together. See *Docker* below.

---

## Setup

```bash
npm install
cp .env.example .env
```

| Variable | Description |
|---|---|
| `VITE_API_BASE_URL` | The API's **origin only**, e.g. `http://localhost:8000`. The `/api/v1` prefix is added in `src/lib/api.js`. |
| `VITE_PAYSTACK_PUBLIC_KEY` | Paystack public key. Not read yet — the gateway checkout is not wired up. |

The backend needs `JWT_SECRET_KEY` set and `ALLOWED_ORIGINS` to include this app's origin, or
the browser will not send the refresh cookie. See `backend/.env.example`.

Seed the backend first — otherwise every read answers with nothing and there is nobody to log in
as:

```bash
cd ../backend && uv run python scripts/seed.py --reset
```

Sign in with `uni-lasu` / `uni-lasu-demo-2026`. Every seeded password follows
`<login id>-demo-2026`; the full list is in `auth.md` §6 at the repository root.

---

## Commands

```bash
npm run dev        # development server → http://localhost:5173
npm run build      # production build → dist/
npm run preview    # preview production build locally
npm test           # Vitest, watch mode
npm run coverage   # coverage report
```

---

## Docker

From the repository root, not here:

```bash
docker compose up                # this app on :5173, the API on :8000, Postgres on :5432
docker compose up frontend       # just this app and what it depends on
docker compose build frontend    # after a package.json change
```

Three things about this setup are worth knowing before the first surprise:

- **`VITE_API_BASE_URL` stays `http://localhost:8000`, not `http://backend:8000`.** The requests
  are made by your browser, which is on the host; `backend` is a name that resolves only inside
  the compose network. It is set in `docker-compose.yaml` and needs no `.env` here.
- **`node_modules` is the container's, not yours.** The bind mount would otherwise cover the
  image's Linux-built tree with the host's Windows-built one, so an anonymous volume is mounted
  at `/app/node_modules` to keep it. A new dependency therefore needs
  `docker compose build frontend` — installing it on the host is invisible to the container.
- **HMR runs on a polling watcher** (`VITE_USE_POLLING`, read by `vite.config.js`). Bind mounts
  from Windows into a Linux container deliver no filesystem events, and without polling a save
  would simply never reach the browser. Running `npm run dev` directly does not poll.

---

## Authentication

Five principals, each signing in with the id the system already minted for them — except a
student, who uses their matric number. There is **no role picker** on the login form: the server
decides what a login id is, and choosing a role first would let somebody pick wrong and be told
their correct password was invalid.

| Role | Base path | Reaches |
|---|---|---|
| `university` | `/university` | Everything |
| `faculty` | `/faculty` | Departments in that faculty, offer chains |
| `department` | `/department` | Programmes, admissions, lecturers, students |
| `lecturer` | `/lecturer` | Own profile, grade submission |
| `student` | `/student` | Own record, registration, ledger |

Three things about how the session is held, each a deliberate departure from the usual pattern:

- **The access token is never decoded here.** `/auth/login` and `/auth/refresh` both return the
  principal in the body, so the token stays opaque — something to put in a header. `jwt-decode`
  is not a dependency.
- **The access token is never persisted.** Only the principal survives a reload, which is enough
  to render a shell. The `HttpOnly` refresh cookie restores the session through a value this code
  cannot read; keeping a bearer token in `localStorage` would buy nothing and hand it to any
  script on the page.
- **`RequireAuth` is not a security boundary.** It decides what to render. Every route is guarded
  server-side, so an edited principal produces a shell whose every request comes back 403.

---

## Structure

```
src/
├── App.jsx                  # five role trees, one page per API route
├── main.jsx                 # providers, Toaster
├── index.css                # tokens, base styles, .surface
├── config/
│   ├── roles.js             # the five roles, exactly as the token names them
│   └── nav.js               # nav per role
├── lib/
│   ├── api.js               # Axios: bearer header, queued 401 refresh, error helpers
│   └── queryClient.js
├── store/
│   ├── authStore.js         # access token (not persisted) + principal (persisted)
│   └── themeStore.js
├── hooks/
│   ├── useAuth.js           # reads the stored principal; decodes nothing
│   └── useTitle.js
├── features/                # one module per bounded context
│   ├── auth/                # login, refresh, /auth/me, credential administration
│   ├── admissions/          # policy, the funnel, an application's life
│   ├── academicRecords/     # transcript, CGPA, corrections
│   ├── billing/             # ledgers, payments, session fees, reconciliation
│   ├── courseCatalog/       # courses, prerequisites, retirement
│   ├── enrollment/          # one route: register for a course
│   ├── facultyDepartment/   # structure, calendar, lecturers, grade submission
│   └── studentProfile/      # the identity anchor
├── layouts/
├── components/
│   ├── ui/                  # Button, Card, Input, Select, Badge, Table, Modal, Feedback
│   ├── Form.jsx             # FormCard + useFields — the shape almost every write takes
│   ├── Sidebar.jsx          # prints the unit you are acting for, under the role
│   ├── Header.jsx
│   ├── BottomNav.jsx
│   ├── PageHeader.jsx       # + StatTile, Detail
│   └── EmptyState.jsx
└── pages/
    ├── public/              # Landing, Login, Apply, NotFound, Unauthorized
    ├── shared/              # Account
    ├── university/
    ├── faculty/
    ├── department/
    ├── lecturer/
    └── student/
```

---

## Things the UI is careful about

These are not style choices. Each one is a place where the obvious rendering would be wrong.

- **A registration refusal is a 200**, and it carries *every* unmet reason rather than the first.
  The page lists them all — a student refused for a prerequisite, who fixes it and is then
  refused for a full course, has queued twice for information the university had both times.
- **Screening and offering are also 200 with an outcome.** "Not qualified" and "no offer
  available" are decisions, not errors, and are not rendered as failures.
- **Capacity and cohort do not add up**, and the admissions page shows them as two blocks with a
  note saying so. Places claimed includes overflow from another programme's chain; the funnel
  includes applicants placed elsewhere.
- **Money and grades are rendered as the strings the API sent.** They are exact decimals; parsing
  them into JavaScript floats to format them would reintroduce the rounding the server avoided.
  Nothing in this app adds up money.
- **Opening a session bills a cohort**, so it is a two-step confirmation and not a toggle.
- **Every attempt at a course appears on the transcript.** Repeats are not collapsed into a best
  attempt — that is the confirmed carry-over rule.
- **Retiring a course does not remove it.** Transcripts refer to courses no longer taught.

## Things the API does not offer, which this app does not fake

- No route lists faculties, departments or sessions. Pages ask for the id you mean rather than
  keeping a second copy of the university's structure that is free to drift.
- No route returns who is registered for a course, so there is no class list.
- No route returns a student's own registrations, so there is no "my courses" table.
- There is no drop or withdraw. When a course may be dropped has never been stated to the system.
- There is no route that changes a student's level.
