# Frontend Library Decisions

## Build Tool

| Package | Version | Reason |
|---|---|---|
| `vite` | latest | Replaces Create React App (`react-scripts`). Faster dev server and builds. |
| `@vitejs/plugin-react` | latest | JSX transform + Fast Refresh for Vite. |

Entry point: `index.html` at project root (not inside `public/`).  
Scripts: `vite` (dev), `vite build`, `vite preview`, `vitest` (test).

---

## Core Framework

| Package | Reason |
|---|---|
| `react@18` | UI framework. |
| `react-dom@18` | DOM renderer. |
| `react-router-dom@6` | Client-side routing. Role-based route sections in `App.jsx`. |

---

## State Management

| Package | Reason |
|---|---|
| `zustand@5` | Auth store — holds JWT access token and `persist` flag. `getUser()` decodes JWT to expose `user_id` and `role`. |
| `@tanstack/react-query@5` | Server state — all API data fetching, caching, and mutations. 1-min stale time. |

No Redux. No Context for server state.

---

## HTTP & Auth

| Package | Reason |
|---|---|
| `axios` | HTTP client. Single instance in `src/lib/api.js` attaches `Authorization: Bearer <token>` on every request. On 401, calls `/auth/refresh`, updates Zustand token, retries once. |
| `jwt-decode` | Decodes JWT in `authStore.getUser()` to read `user_id` and `role` without a round-trip. |

---

## Forms & Validation

| Package | Reason |
|---|---|
| `react-hook-form` | Form state management. Replaces controlled-input boilerplate. Used for all forms (application, registration, profile, score entry, etc.). |
| `zod` | Schema validation. Defines field rules and error messages. |
| `@hookform/resolvers` | Bridges Zod schemas into `react-hook-form` via `zodResolver`. |

---

## File Uploads

| Package | Reason |
|---|---|
| `react-dropzone` | Drag-and-drop file upload UI. Used for document uploads (admission, thesis, assignment submissions). |

PDF downloads (transcript, receipt, admission letter) are generated server-side and returned as a URL — no client-side PDF library needed.

---

## Styling

| Package | Reason |
|---|---|
| `tailwindcss@3` | Utility-first CSS. Custom color palette defined in `tailwind.config.js`. |
| `postcss` | Required by Tailwind. |
| `autoprefixer` | Required by Tailwind. |

No custom color tokens — uses Tailwind's built-in `indigo`, `violet`, and `slate` scales directly. See **Design System** section below.

Additional packages:
| Package | Reason |
|---|---|
| `@fontsource/inter` | Self-hosted Inter font. No Google Fonts network request at runtime. |

---

## UI Utilities

| Package | Reason |
|---|---|
| `react-hot-toast` | Toast notifications for mutation feedback (success/error). Replaces modal-based approach for non-critical feedback. |
| `date-fns` | Date formatting and calculation for academic calendar, deadlines, and semester dates. |

---

## Charts & Data Display

| Package | Reason |
|---|---|
| `recharts` | Charts for analytics dashboards (enrollment stats, pass/fail rates, CGPA distribution, fee collection). |
| `@tanstack/react-table` | Headless table primitives for data-heavy admin views (applications list, student records, fee reports). Handles sorting, filtering, and pagination. |

---

## Payments

| Package | Reason |
|---|---|
| `react-paystack` | Paystack payment integration. Used for tuition fees, application fees, acceptance fees, accommodation fees. |

---

## WebSocket

No library. The backend uses FastAPI native WebSocket — plain JSON over `ws://`.  
Use the native browser `WebSocket` API directly.

Two endpoints:
- `ws://.../chat/{section_id}?token=<access_token>` — course group chat (bidirectional JSON)
- `ws://.../notifications?token=<access_token>` — per-user push (receive-only, send pings to keep alive)

---

## Testing

| Package | Reason |
|---|---|
| `vitest` | Vite-native test runner. Replaces Jest from `react-scripts`. |
| `jsdom` | DOM environment for Vitest. |
| `@testing-library/react` | Component testing utilities. |
| `@testing-library/jest-dom` | Custom DOM matchers (`toBeInTheDocument`, etc.). Compatible with Vitest. |
| `@testing-library/user-event` | Simulates user interactions in tests. |
| `@vitest/coverage-v8` | Coverage reports. |

---

## Environment Variables

Vite uses `VITE_*` prefix, accessed via `import.meta.env`.

```
VITE_API_BASE_URL=...
VITE_PAYSTACK_PUBLIC_KEY=...
```

`process.env.NODE_ENV` → `import.meta.env.MODE`

---

## Design System

### Color Palette

All colors use Tailwind built-in scales — no custom hex values in `tailwind.config.js`.

#### Light Mode

| Role | Tailwind token | Hex |
|---|---|---|
| Page background | `slate-50` | #F8FAFC |
| Card / surface | `white` | #FFFFFF |
| Border | `slate-200` | #E2E8F0 |
| Text primary | `slate-900` | #0F172A |
| Text secondary | `slate-500` | #64748B |
| Text muted | `slate-400` | #94A3B8 |
| Primary action | `indigo-600` | #4F46E5 |
| Primary hover | `indigo-700` | #4338CA |
| Primary subtle bg | `indigo-50` | #EEF2FF |
| Accent | `violet-500` | #8B5CF6 |
| Success | `emerald-600` / `emerald-50` | |
| Warning | `amber-500` / `amber-50` | |
| Danger | `red-600` / `red-50` | |

#### Dark Mode

| Role | Tailwind token |
|---|---|
| Page background | `slate-950` |
| Card / surface | `slate-900` |
| Border | `slate-700` |
| Text primary | `slate-100` |
| Text secondary | `slate-400` |
| Primary action | `indigo-400` (lighter for dark bg contrast) |
| Primary hover | `indigo-300` |
| Primary subtle bg | `indigo-950` |
| Accent | `violet-400` |
| Success | `emerald-400` / `emerald-950` |
| Warning | `amber-400` / `amber-950` |
| Danger | `red-400` / `red-950` |

#### Sidebar (dark in both light and dark mode)

| Role | Tailwind token |
|---|---|
| Background | `indigo-950` |
| Text | `slate-300` |
| Active item background | `indigo-700` |
| Active item text | `white` |
| Muted icons | `slate-500` |

---

### Typography

- **Font family:** Inter (`@fontsource/inter`) — imported once in `src/index.css`
- **Default size:** `text-sm` (14px) for data-dense views; `text-base` for forms and content pages
- **Page titles:** `text-xl font-semibold text-slate-900 dark:text-slate-100`
- **Card titles:** `text-sm font-medium text-slate-700 dark:text-slate-300`
- **Muted labels:** `text-xs text-slate-500 dark:text-slate-400`
- **Monospace:** `font-mono text-sm` for matric numbers, IDs, course codes

---

### Shapes & Elevation

| Element | Classes |
|---|---|
| Cards | `rounded-xl shadow-sm` (light) / `rounded-xl border border-slate-800` (dark) |
| Buttons | `rounded-lg` |
| Inputs | `rounded-lg` |
| Badges | `rounded-full text-xs font-medium px-2 py-0.5` |
| Modals | `rounded-2xl shadow-2xl` |
| Dropdowns | `rounded-xl shadow-lg` |

---

### Button Variants

| Variant | Classes |
|---|---|
| Primary | `bg-indigo-600 hover:bg-indigo-700 text-white` |
| Secondary | `bg-white border border-slate-200 hover:bg-slate-50 text-slate-700` |
| Danger | `bg-red-600 hover:bg-red-700 text-white` |
| Ghost | `hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400` |
| Link | `text-indigo-600 dark:text-indigo-400 hover:underline` |

All buttons: `text-sm font-medium transition-colors duration-150`.

---

### Responsive Layout

| Breakpoint | Layout |
|---|---|
| Mobile `< 768px` | No sidebar. **Bottom tab nav** for `student` and `applicant` (max 5 tabs). **Hamburger drawer** for all admin roles (`registrar`, `bursar`, `hod`, `dean`, `super_admin`, `lecturer`). Data tables collapse to stacked card lists. |
| Tablet `768px – 1024px` | Sidebar visible as icon-only strip (collapsed). Hover/click expands to full 240px. |
| Desktop `> 1024px` | Fixed sidebar 240px + scrollable content area. |

---

### Dark Mode

Enabled via Tailwind's `class` strategy (`darkMode: 'class'` in `tailwind.config.js`).  
Toggled by adding/removing the `dark` class on `<html>`. Default follows `prefers-color-scheme` on first load, then persists to `localStorage`.

---

## Not Used (and Why)

| Rejected | Reason |
|---|---|
| `react-scripts` (CRA) | Replaced by Vite. |
| `socket.io-client` | Backend uses plain WebSocket, not Socket.IO protocol. |
| `@react-pdf/renderer` | PDFs generated server-side; client only downloads via URL. |
| `moment` | Replaced by `date-fns` (smaller, tree-shakeable). |
| Redux / RTK | Replaced by Zustand (auth) + TanStack Query (server state). |
| `web-vitals` | CRA-specific, not needed with Vite. |
