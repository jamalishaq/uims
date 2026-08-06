# Authentication & Authorization — the decisions

This file is the written form of the decisions the identity work is built on. It exists
because CLAUDE.md section 6 asks for exactly that: the actors and what each may do were
confirmed with a human long before anything was built, and the note beside them read
**"Not built yet."** This is the change that builds it, and the decisions it turns into code
are recorded here rather than inferred from the code afterwards.

Everything below marked **Confirmed** was decided by a human. Everything marked **Open** was
deliberately not guessed.

---

## 1. Identity is the eighth bounded context

CLAUDE.md section 6 already settled the shape:

> Identity is a separate context holding credentials, role and scope only — never names or
> bio-data, which would make it the second identity system
> `academic_records/domain/academic_record.py` warns about.

So `src/identity/` is a bounded context like the other seven, with the same four layers, and
it obeys the same dependency rule. It holds a `Credential` and nothing else. It does not know
a lecturer's rank, a student's programme or a faculty's name; it knows that a login id maps to
a password hash, a role, a scope and the id of a principal some *other* context owns.

`tests/architecture/test_dependency_rule.py`'s `EXPECTED_CONTEXTS` gains `identity`, and the
count in every docstring that said "seven contexts" moves to eight.

### Why the guard is not in the identity context

Every router in the system has to be able to ask "who is calling, and may they?". If that
dependency lived in `identity/`, then `billing`'s router importing it would be a cross-context
import and rule (b) would — correctly — reject it.

So the *verification* half lives in a new flat module, **`src/security.py`**, beside
`http_api.py`, `persistence.py` and `event_bus.py`. It imports no context. It holds the token
codec, the `Principal` a decoded token becomes, and the FastAPI dependencies routers guard
themselves with. This is the same argument `http_api.py` makes in its own docstring — "this is
transport, not a context" — and it is why a router may import it exactly as it already imports
`dependencies_of`.

The *issuing* half stays in `identity/`, because deciding that a password was correct and a
token is therefore owed is a use case, not transport.

The two vocabularies are kept honest by a test rather than by a shared import: `security.Role`
and `identity.domain.values.Role` are asserted to have identical members. Merging them into
one enum would mean either the domain importing a flat module (rule (c): the domain layer is
stdlib-only) or every context importing identity (rule (b)). Two enums and an assertion is the
cheaper of the two prices, and it is the arrangement
`tests/academic_records/domain/test_grading_scale.py` already uses for the grading table.

---

## 2. Who logs in — **Confirmed**

Five principals, one credential each per unit, and the login id **is** the unit's own id.

| Role | Login id looks like | Scope | What it is |
|---|---|---|---|
| `university` | `UNI-LASU` | the university | The bursary and the registry acting university-wide |
| `faculty` | `FAC-SCI` | one faculty id | The faculty officer |
| `department` | `DEPT-CSC` | one department id | The department registrar |
| `lecturer` | the lecturer id | themselves | A lecturer |
| `student` | **the matric number** | themselves | A student |

A student logs in with their matric number because that is the number they are given and the
one the bursary and the gateway already quote. Everyone else logs in with the id the system
minted for the thing they are.

This is a deliberate simplification and it is worth naming: a *faculty* does not log in, a
person does. What is modelled here is one shared office account per unit, not a named
office-holder. `Credential` is shaped so that a named holder can be added later — it already
separates `login_id` (what you type) from `principal_id` (what you are) from `scope` (what you
may reach) — but nothing today issues two credentials for one unit.

### Roles map onto the actors section 6 already confirmed

| CLAUDE.md actor | Role here |
|---|---|
| department registrar | `department` |
| faculty officer | `faculty` |
| bursar | `university` |
| lecturer | `lecturer` |
| student | `student` |

The bursar is university-scoped in section 6 ("*bursar* — university-scoped: fee schedules,
session fees, reconciliation, ledger reads"), which is why there is no separate `bursar` role:
it would be a second role with exactly one scope and exactly the university's reach, and two
names for one set of permissions is how they start to disagree.

---

## 3. What a token carries — **Confirmed**

A JWT, HS256, signed with `JWT_SECRET_KEY` from the environment. Claims:

```
sub          the principal id — the lecturer id, the student id, the department id
login_id     what they typed
role         one of the five above
scope_kind   "university" | "faculty" | "department" | "lecturer" | "student"
scope_id     the id the scope names; for university, the university's own id
typ          "access" | "refresh"
iat / exp    issued-at and expiry
```

**No name, no email, no bio-data.** The token carries what authorization reads and nothing
else, for the reason section 6 gives about the identity context itself: a token holding a
student's name would be a second place the university's record of who somebody is lives, and
the two would drift.

- **Access token: 30 minutes.** Short enough that a leaked one is a bounded problem, long
  enough that a session survives a form being filled in.
- **Refresh token: 12 hours**, delivered as an `HttpOnly`, `SameSite=Lax` cookie and never
  readable by JavaScript. `POST /auth/refresh` exchanges it for a new access token.

**Open, and not guessed: revocation.** There is no server-side refresh-token store, so a
refresh token cannot be revoked before it expires — logging out clears the cookie and the
client's access token, which ends the session on that browser and not on a stolen copy. Adding
rotation with a stored family id is the standard fix and is a decision about how much a
12-hour window costs, which nobody has stated. It is recorded here rather than quietly
implemented as though it were free.

---

## 4. Passwords — **Confirmed**

`hashlib.scrypt`, per-credential 16-byte salt, stored as
`scrypt$16384$8$1$<salt-b64>$<hash-b64>`. Verified with `hmac.compare_digest`.

Two reasons for scrypt over the usual `bcrypt`/`argon2` dependency:

1. It is **stdlib**, and `PasswordHash` is a value object in `identity/domain/`, where rule (c)
   of the fitness test permits stdlib only. A domain type that could not hash its own password
   would have to hand the plaintext outwards to something that could, which is the one
   direction a password must never travel.
2. It is memory-hard, which is the property that matters, and the cost parameters are stored
   *in the hash string* — so raising them later re-hashes on next login instead of invalidating
   every credential.

`PasswordHash` never holds or logs the plaintext, and `Credential.__repr__` does not print the
hash.

---

## 5. Enforcement — **Confirmed: everywhere, in two tiers**

Before this change, CLAUDE.md said in three separate places that the API had no authentication
and that "routes that write money or transcripts are reachable by anyone who can reach the
process." Every route under `/api/v1` now requires a valid access token, with the deliberate
exceptions listed below.

Authorization is enforced in two tiers, and the split is not laziness — it is the boundary of
what a context can honestly check.

**Tier 1 — the role gate, on every route.** Which *kind* of actor may perform this kind of
act. `POST /faculty-department/faculties` is `university`; `POST /billing/session-fees` is
`university`; `POST /faculty-department/grade-submissions` is `lecturer`. This is a static
fact about the route and is checked without reading anything.

**Tier 2 — the scope gate, where the request names the scope.** A department registrar's
permission is meaningless without *which department*, which is section 6's whole point about
scoped RBAC. Where the request itself carries the unit the token is scoped to, the two are
compared and a mismatch is a 403:

- `/faculty-department/departments/{department_id}/…` against a `department` token's scope
- `POST /faculty-department/departments` against the `faculty_id` in the body
- `/student-profile/students/{student_id}` and `/academic-records/records/{student_id}` against
  a `student` token's own id
- `/faculty-department/lecturers/{lecturer_id}/…` against a `lecturer` token's own id
- `/billing/accounts/{party_id}` against a `student` token's own id or matric number

A `university` token satisfies every scope check. That is what university-scoped means.

**Where tier 2 deliberately does not reach: program-keyed routes.** Most of Admissions is keyed
by `program_id` — quotas, entry requirements, screening, offers, the applicant lists. Checking
that a `department` token may act on a given program means resolving program → department, and
**Admissions cannot do that**: CLAUDE.md is explicit that "an `Applicant` carries programs and
never a department", and Admissions has no port into Faculty & Department that would answer it.
Adding one is a new cross-context dependency, which section 6 says to escalate rather than
invent.

So those routes carry the role gate only, and the gap is recorded rather than papered over. The
honest statement is: **a department registrar can currently act on another department's
programs.** Closing it needs either a `ProgramOwnershipPort` from Admissions into Faculty &
Department, or the scope check moved to a gateway that can resolve it — and which of those the
university wants is not something this change may decide.

### Routes that stay public, and why

- `POST /admissions/applications` — the public application form. Somebody who has never had an
  account applies here; requiring one would be a deadlock.
- `POST /billing/webhooks/paystack` — the gateway does not hold a university credential. It is
  already authenticated, by signature, and CLAUDE.md is emphatic that verification happens
  before the payload reaches a use case. **That ordering is unchanged by this work.**
- `POST /auth/login`, `POST /auth/refresh` — the doors themselves.
- `GET /health` — a liveness probe that needed a token would take the API out of rotation
  whenever the signing key rotated.

### Accepting and declining an offer

`POST /applicants/{id}/acceptance` and `/declination` are guarded as `department`, not left
public. This is a **deviation to revisit** and is flagged as such: section 6's confirmed actor
list gives the department registrar screening, the offer decision and matriculation, and says
nothing about recording an applicant's answer. But there is no applicant identity in the
confirmed set, and the alternative was leaving a route that cancels somebody's admission open
to anonymous callers. A registrar recording the answer is the smaller invention. **Open:**
whether applicants get credentials of their own.

---

## 6. Seeded credentials

`scripts/seed.py` writes one credential per unit it creates, so the demo university can be
logged into at every level. Every password is `<role>-demo-2026` and every one of them is a
**development fixture** — the seeder already carries that warning for its fee amounts and
quotas, and it applies here at least as strongly. The seeder refuses to run against a database
whose URL does not look local unless `--i-know-this-is-not-local` is passed.

---

## 7. What this does not change

- **Domain-level authorization stays where it is.** `GradeSubmission.submit()` checking
  `lecturer.is_assigned_to(course)` is not replaced by a role check, and the role gate on the
  route does not weaken it. Section 6 states the rule this follows: *authorization lives in the
  domain when the deciding context owns the data the check reads, and at the edge when it does
  not.* A lecturer token gets you to the route; the domain still decides whether you teach the
  course.
- **Scope still travels as explicit path parameters.** Section 6 asked for this in advance —
  "so that a token later *constrains* a filter rather than supplying an identity" — and it is
  why no route was rewritten to read its subject off the token. A student reads their record at
  `/records/{student_id}` with their own id in the path, and the token is checked against it.
  Routes did not change shape; they gained a guard.
- **The webhook path.** Not touched, beyond being excluded from the bearer requirement.
