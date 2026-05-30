# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Frontend (run from sms/lms/)
npm start           # Development server at http://localhost:3000
npm test            # Run tests in watch mode
npm run build       # Production build to build/

# Backend (run from sms/lms_api/)
python manage.py runserver       # Dev server
python manage.py makemigrations
python manage.py migrate
```

## What This Is

A React + Django REST Framework School LMS supporting five user roles: **Admin, Teacher, Student, Applicant, Secretary**. Frontend connects to backend at `https://lms-api-xi.vercel.app/api/v1` (configured via `lms/.env` → `REACT_APP_API_BASE_URL`).

Features: class management, assignments, exams, attendance, study groups, Paystack tuition payments, WebSocket group chat and notifications.

## Frontend Architecture

### Role-Based Routing

`src/App.js` contains all routes organized by role. Every authenticated route is wrapped in `RequireAuth` (checks JWT role) and `PersistLogin` (handles token refresh on page load). Each role renders inside `UserLayout` with a `urlSegments` prop for sidebar navigation.

```
PersistLogin
└── RequireAuth (allowed: ["Student"])
    └── UserLayout (urlSegments: studentLinks)
        └── <Outlet /> → role-specific pages
```

### State Management

**Zustand** (`src/store/authStore.js`) — single store with:
- `token` — JWT access token (persisted to localStorage)
- `persist` — "Remember Me" flag
- `getUser()` — decodes the JWT to expose `username`, `role`, `user_id`, `class_id`, `is_form_teacher`, `has_made_payment`, `term_id`

**TanStack Query** (`src/lib/queryClient.js`) — server state cache with 1-min stale time.

**Axios instance** (`src/lib/api.js`):
- Attaches `Authorization: Bearer <token>` from Zustand on every request
- On 401, calls `/auth/refresh` (httpOnly cookie), updates the token in Zustand, and retries once

### JWT / Auth Flow

- `useAuth()` (`src/hooks/useAuth.js`) — calls `useAuthStore().getUser()` to decode the in-memory JWT
- `usePersist()` (`src/hooks/usePersist.js`) — returns `[persist, setPersist]` from Zustand
- `PersistLogin` — on mount, if `persist=true` and no token, calls `/auth/refresh` via axios directly

### Feature Module Pattern

Each domain follows this structure:
```
src/features/[domain]/
  queries.js       ← TanStack Query hooks (useXxx, useAddXxx, useUpdateXxx, useDeleteXxx)
  [Domain]List.js  ← list/table component
  [Domain]Form.js  ← create/edit form
  ...
```

Hook naming convention:
- Queries: `useTeachers()`, `useTeacher(id)`, `useStudents(classId?)`
- Mutations: `useAddTeacher()`, `useUpdateTeacher()`, `useDeleteTeacher()`

Mutation usage (TanStack v5 style):
```js
const { mutate: addTeacher, isPending, isSuccess, isError, error } = useAddTeacher()
// error shape: error?.response?.data?.message || error?.message
```

Query usage (plain arrays, no entity adapters):
```js
const { data: teachers = [], isLoading, isError, error } = useTeachers()
// For single item: const { data: teacher } = useTeacher(id)
```

### Component Organization

- `src/pages/[role]/` — full-page route components
- `src/features/[domain]/` — domain-specific UI + query hooks
- `src/components/` — shared UI (Header, Sidebar, modals, loaders)
- `src/layouts/` — structural wrappers (`UserLayout`, `AppLayout`)
- `src/hooks/` — `useAuth`, `usePersist`, `useTitle`
- `src/store/` — `authStore.js` (Zustand)
- `src/lib/` — `api.js` (Axios), `queryClient.js` (TanStack QueryClient)

### Styling

Tailwind CSS with custom colors in `tailwind.config.js`:
- `ds-blue` (#0F2942), `md-blue` (#176FB2), `bs` (#3498DB), `lp-blue` (#C1DFF6), `vl-blue` (#F2F8FD)

## Backend Architecture

Django REST Framework + SimpleJWT + Django Channels (Daphne).

### Key Files

- `lms_api/api/settings.py` — all secrets via `python-decouple` from `.env`
- `lms_api/school/models.py` — all models (User, Student, Teacher, Class, Subject, Score, etc.)
- `lms_api/school/serializers.py` — explicit imports only, no wildcard
- `lms_api/school/views/` — organized by domain; views use `rest_framework_roles` for per-method RBAC
- `lms_api/school/signals.py` — post_save hooks for notifications, score updates, applicant admission
- `lms_api/school/consumers.py` — `ChatConsumer` (auth-gated WebSocket) + `NotificationConsumer`
- `lms_api/school/urls.py` — all paths under `/api/v1/` (prefix set in `api/urls.py`)

### Auth Flow

Login → `CustomTokenObtainPairView` sets refresh token as httpOnly cookie and returns access token in body. Access token lifetime: 60min. Refresh: `/auth/refresh` reads cookie.

### Adding New Features

**Frontend:**
1. Create `src/features/[domain]/queries.js` with TanStack Query hooks calling `api.get/post/put/delete`
2. Build UI components importing from `queries.js`
3. Add routes in `src/App.js` under the appropriate role section
4. Add sidebar links via the role's `urlSegments` array

**Backend:**
1. Add model in `school/models.py` + run migrations
2. Add serializer in `school/serializers.py`
3. Add view in `school/views/[domain]_views.py` using `rest_framework_roles` for permissions
4. Register URL in `school/urls.py`
5. Export view from `school/views/__init__.py`
