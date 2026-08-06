# Seeded credentials

The nineteen logins `backend/scripts/seed.py` writes, enumerated. `auth.md` §6 gives the same
set as patterns (`lec-001` … `lec-006`); this is the list with the ids and the people behind
them, so a page can be opened as the principal it was built for without working out who that is.

> **Every password here is a development fixture.** They are written in the seeder, printed by
> it on every run, and identical on every machine that has ever run it. They authenticate a
> demo university in a local container and nothing else. A deployment that accepted any of them
> is a deployment that was seeded with `--i-know-this-is-not-local`, which is the flag that
> exists to make that impossible by accident.

The rule is **`<login id lowercased>-demo-2026`** — so the password is always the login id with
`-demo-2026` after it, including for students, whose login id is their matric number.

Regenerate the underlying data with:

```bash
docker compose run --rm backend python scripts/seed.py --reset
```

---

## University — 1

Section 6's *bursar*, university-scoped: fee schedules, session fees, reconciliation, ledger
reads. The only principal that can open a session, which is what bills a cohort.

| Login | Password | Principal | Scope |
|---|---|---|---|
| `uni-lasu` | `uni-lasu-demo-2026` | `uni-lasu` | university |

## Faculty — 2

Owns the `AlternativeProgramPolicy` chains for programs in its faculty — a chain spends *other
departments'* quota, so one department must not point at another's places unilaterally.

| Login | Password | Faculty | Departments under it |
|---|---|---|---|
| `fac-sci` | `fac-sci-demo-2026` | Faculty of Science (`SCI`) | CSC, MTH, PHY |
| `fac-eng` | `fac-eng-demo-2026` | Faculty of Engineering (`ENG`) | EEE |

## Department — 4

Sets quota and entry requirements for its programs, runs screening and the offer decision (both
automatic), and matriculates accepted, fee-cleared applicants.

| Login | Password | Department | Faculty | Program |
|---|---|---|---|---|
| `dept-csc` | `dept-csc-demo-2026` | Computer Science (`CSC`) | `fac-sci` | `prog-csc` — B.Sc. Computer Science |
| `dept-mth` | `dept-mth-demo-2026` | Mathematics (`MTH`) | `fac-sci` | `prog-mth` — B.Sc. Mathematics |
| `dept-phy` | `dept-phy-demo-2026` | Physics (`PHY`) | `fac-sci` | `prog-phy` — B.Sc. Physics |
| `dept-eee` | `dept-eee-demo-2026` | Electrical and Electronic Engineering (`EEE`) | `fac-eng` | `prog-eee` — B.Eng. Electrical and Electronic Engineering |

## Lecturer — 6

Scoped to themselves. A lecturer may submit a grade only for a course they are assigned to —
checked in the domain against Faculty & Department's own assignment records, not by role.

| Login | Password | Name | Department |
|---|---|---|---|
| `lec-001` | `lec-001-demo-2026` | Dr Adaeze Okonkwo | Computer Science |
| `lec-002` | `lec-002-demo-2026` | Dr Chinedu Alabi | Computer Science |
| `lec-003` | `lec-003-demo-2026` | Prof Bola Ajayi | Mathematics |
| `lec-004` | `lec-004-demo-2026` | Dr Yusuf Garba | Mathematics |
| `lec-005` | `lec-005-demo-2026` | Dr Ifeoma Nnaji | Physics |
| `lec-006` | `lec-006-demo-2026` | Engr Tayo Sobowale | Electrical and Electronic Engineering |

## Student — 6

Scoped to themselves, and **the login id is the matric number** — `260591001` is entry year 26,
department code 0591 (CSC), first in that department's intake. The `stu-000n` id is Student
Profile's internal key and is not what anybody types.

| Login (matric no.) | Password | Name | Program | Student id |
|---|---|---|---|---|
| `260591001` | `260591001-demo-2026` | Adaeze Okonkwo | B.Sc. Computer Science | `stu-0001` |
| `260591002` | `260591002-demo-2026` | Chidi Nwosu | B.Sc. Computer Science | `stu-0002` |
| `260591003` | `260591003-demo-2026` | Halima Bello | B.Sc. Computer Science | `stu-0003` |
| `260592001` | `260592001-demo-2026` | Emeka Obi | B.Sc. Mathematics | `stu-0004` |
| `260593001` | `260593001-demo-2026` | Folake Adeyemi | B.Sc. Physics | `stu-0005` |
| `260594001` | `260594001-demo-2026` | Ibrahim Sani | B.Eng. Electrical and Electronic Engineering | `stu-0006` |

All six are at entry level 100 in session `sess-2026-2027`. Nothing in the system advances a
level — what does, and when, is an institutional fact nobody has stated.

### Financial clearance differs per student, on purpose

Clearance is **≥70% of the session fee to register for first semester, 100% for second**. The
seeder spreads the six across that rule, so which student you log in as decides what registration
does:

| Login | Session fee settled | First semester | Second semester |
|---|---|---|---|
| `260591001` | 100% | clears | clears |
| `260592001` | 100% | clears | clears |
| `260591002` | 70% | clears | **refused** |
| `260593001` | 70% | clears | **refused** |
| `260591003` | 0% | **refused** | **refused** |
| `260594001` | *no charge at all* | **refused** | **refused** |

`260594001` is the interesting one: the seeded fee schedule prices no session fee for `prog-eee`
at level 100, so the charge was skipped entirely, and Billing answers *not cleared* for a party
with no session-fee charge on record rather than waving them through. A hole in the bursary's
schedule blocks a student instead of quietly clearing them.

So `260591001` is the account to use for a registration that should succeed, `260591003` for
`NOT_FINANCIALLY_CLEARED`, and `260591002` for the case that clears one semester and not the
next.

---

## Who does not get a login

**Applicants.** There is no applicant role, so the eight seeded applicants — including
`app-0007` and `app-0008`, who hold billing accounts but never matriculated — cannot log in at
all. Accepting and declining an offer are therefore guarded as `department`: the registrar
recording the answer, rather than the applicant giving it. `auth.md` records that as an open
decision rather than a settled one, taken because the alternative was leaving a route that
cancels somebody's admission open to anonymous callers.

Two other gaps worth knowing before a login surprises you:

- **A matriculated student does not automatically get a credential.** Identity subscribes to
  nothing, `StudentMatriculated` included, because a password this system invented and told
  nobody is not a credential. The six above exist only because the seeder wrote them last, after
  matric numbers existed to log in with.
- **A department registrar can act on another department's *programs*.** Most of Admissions is
  keyed by `program_id`, and Admissions cannot resolve a program to a department, so those
  routes carry a role gate and no scope check. Closing it needs a cross-context port.
