# Frontend — University Management System

React 18 + Vite + TanStack Query + Zustand + Tailwind CSS.

---

## Requirements

- Node.js 18+
- npm 9+

---

## Setup

```bash
npm install
```

Copy the environment file and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `VITE_API_BASE_URL` | Backend API base URL, e.g. `http://localhost:8000/api/v1` |
| `VITE_WS_BASE_URL` | WebSocket base URL, e.g. `ws://localhost:8000/ws` |
| `VITE_PAYSTACK_PUBLIC_KEY` | Paystack public key |

---

## Commands

```bash
npm run dev        # development server → http://localhost:5173
npm run build      # production build → dist/
npm run preview    # preview production build locally
npm test           # run tests with Vitest (watch mode)
npm run coverage   # test coverage report
```

---

## Structure

```
src/
├── App.jsx                  # all routes, organised by role
├── main.jsx                 # entry point — providers, Toaster
├── index.css                # Inter font + Tailwind directives
├── config/
│   ├── roles.js             # role constants, ROLE_HOME, ROLE_BASE
│   └── nav.js               # sidebar/bottom-nav links per role
├── lib/
│   ├── api.js               # Axios instance (auth header + 401 refresh)
│   └── queryClient.js       # TanStack QueryClient config
├── store/
│   ├── authStore.js         # JWT token + rememberMe (Zustand)
│   └── themeStore.js        # dark mode toggle (Zustand)
├── hooks/
│   ├── useAuth.js           # decodes JWT → { user_id, role, ... }
│   └── useTitle.js          # sets document.title
├── features/
│   ├── auth/                # PersistLogin, RequireAuth, login/logout queries
│   ├── academic/            # faculties, departments, programs, sessions
│   ├── admission/           # applications, decisions, enrolment
│   ├── assignments/         # create, submit, grade
│   ├── attendance/          # mark attendance, summary
│   ├── courses/             # courses, sections, prerequisites
│   ├── enrollment/          # student course registration
│   ├── exams/               # timetable, exam slots
│   ├── fees/                # fee schedule, Paystack payments
│   ├── grades/              # score submission, GPA, transcript
│   ├── hostel/              # application, room allocation
│   ├── library/             # catalog, borrow, return
│   ├── notifications/       # list, create
│   ├── reports/             # enrollment stats, pass/fail, fee collection, CGPA
│   ├── staff/               # staff directory
│   ├── students/            # student records, status
│   ├── thesis/              # register, submit, review
│   └── transcript/          # transcript download
├── layouts/
│   ├── AppLayout.jsx        # root layout wrapper
│   └── UserLayout.jsx       # sidebar + header + mobile nav
├── components/
│   ├── ui/                  # Button, Card, Badge, Input, Select, Modal, Spinner
│   ├── Sidebar.jsx          # desktop/tablet nav (indigo-950 bg)
│   ├── Header.jsx           # top bar — dark toggle, notifications, user chip
│   ├── BottomNav.jsx        # mobile nav for student / applicant / alumni
│   ├── PageHeader.jsx       # page title + subtitle + action slot
│   └── EmptyState.jsx       # empty list placeholder
└── pages/
    ├── public/              # Login, Apply, NotFound, Unauthorized
    ├── student/
    ├── applicant/
    ├── lecturer/
    ├── hod/
    ├── dean/
    ├── registrar/
    ├── bursar/
    ├── super_admin/
    └── alumni/
```

---

## Roles

| Role | Base path | Mobile nav |
|---|---|---|
| `student` | `/student` | Bottom tabs |
| `applicant` | `/applicant` | Bottom tabs |
| `alumni` | `/alumni` | Bottom tabs |
| `lecturer` | `/lecturer` | Hamburger drawer |
| `hod` | `/hod` | Hamburger drawer |
| `dean` | `/dean` | Hamburger drawer |
| `registrar` | `/registrar` | Hamburger drawer |
| `bursar` | `/bursar` | Hamburger drawer |
| `super_admin` | `/admin` | Hamburger drawer |
