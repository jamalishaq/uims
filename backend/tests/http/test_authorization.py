"""Who may call what, and the check that keeps the other suites honest.

Every other HTTP module drives the app through a **university-scoped** client, because those
tests are about what a route does rather than who may reach it. The cost of that convenience is
that a route which lost its guard entirely would still pass all of them, silently. So the first
test here does not exercise any route: it walks the mounted ones and asserts each is either
guarded or named in :data:`PUBLIC`, by exact path. Removing a guard therefore fails a test, and
the only way to make it pass is to add the path to a list with a reason beside it.

The rest is the two tiers ``auth.md`` describes, exercised: the role gate on a handful of
representative routes, and the scope gate wherever the request names a unit the token can be
compared against.
"""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from tests.http.conftest import api_routes

import security

PUBLIC = frozenset(
    {
        "/health",
        "/auth/login",
        "/auth/refresh",
        "/auth/logout",
        "/admissions/applications",
        "/billing/webhooks/paystack",
    }
)
"""Every route reachable without a bearer token, by exact path, each for a stated reason.

- ``/health`` — a probe that needed a token would take the API out of rotation the moment the
  signing key rotated, which is the opposite of what a liveness probe is for.
- ``/auth/login`` and ``/auth/refresh`` — the doors. A door that required a key to open would
  not be one.
- ``/auth/logout`` — clearing a cookie. Requiring a valid token would refuse exactly the caller
  who most needs it, one whose access token has already expired, and leave the cookie in place.
- ``/admissions/applications`` — the public application form. Somebody who has never had an
  account applies through it; requiring one would be a deadlock.
- ``/billing/webhooks/paystack`` — the gateway holds no university credential. It is already
  authenticated, by signature, before the payload reaches any use case, and CLAUDE.md section 4
  is emphatic that the ordering there is not to be disturbed.

A frozenset of exact paths rather than a prefix rule: ``/auth/*`` as a pattern would have
quietly published ``/auth/credentials``, which issues logins.
"""


def guards_of(route) -> set[str]:
    """The names of the ``security`` callables a route depends on, however deeply nested.

    FastAPI flattens a route's dependencies into a tree of ``Dependant``; a guard may be the
    route's own parameter annotation or something a sub-dependency pulled in. Walking the tree
    rather than reading the signature is what makes this check survive a refactor that moves a
    guard behind a shared dependency.
    """
    found: set[str] = set()
    pending = [route.dependant]
    while pending:
        dependant = pending.pop()
        call = getattr(dependant, "call", None)
        if call is not None and getattr(call, "__module__", "") == security.__name__:
            found.add(call.__qualname__)
        pending.extend(dependant.dependencies)
    return found


def test_the_guard_walk_finds_a_guard_it_should(app: FastAPI) -> None:
    """Guard for the guard: a walk that found nothing would pass the test below vacuously."""
    faculties = next(
        route for route in api_routes(app) if route.path.endswith("/faculty-department/faculties")
    )
    assert guards_of(faculties), "the walk found no security dependency on a route that has one"


def test_every_route_is_guarded_or_deliberately_public(app: FastAPI) -> None:
    """The check the rest of the HTTP suite cannot make for itself.

    Every other module authenticates as the university, so a route with no guard at all behaves
    identically to a correctly guarded one under those tests. This is what notices.
    """
    unguarded = sorted(
        route.path
        for route in api_routes(app)
        if not guards_of(route) and route.path.removeprefix("/api/v1") not in PUBLIC
    )
    assert unguarded == [], (
        "these routes accept an unauthenticated caller and are not in PUBLIC: "
        f"{', '.join(unguarded)}"
    )


def test_the_public_list_names_only_routes_that_exist(app: FastAPI) -> None:
    """A stale entry would be an exemption nobody notices has stopped applying to anything."""
    mounted = {route.path.removeprefix("/api/v1") for route in api_routes(app)}
    assert mounted >= PUBLIC, f"PUBLIC names routes that are not mounted: {PUBLIC - mounted}"


# ---- authentication ----


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/student-profile/students/stu-1"),
        ("get", "/academic-records/records/stu-1"),
        ("get", "/billing/accounts/stu-1"),
        ("post", "/faculty-department/faculties"),
        ("post", "/course-catalog/courses"),
        ("post", "/enrollment/registrations"),
        ("get", "/auth/me"),
    ],
)
async def test_a_guarded_route_refuses_an_anonymous_caller(
    anonymous_client: AsyncClient, api: str, method: str, path: str
) -> None:
    call = getattr(anonymous_client, method)
    response = await (call(f"{api}{path}", json={}) if method == "post" else call(f"{api}{path}"))
    assert response.status_code == 401, response.text
    assert response.json()["error"] == "AuthenticationRequiredError"


async def test_a_forged_token_is_refused(
    anonymous_client: AsyncClient, api: str, app: FastAPI
) -> None:
    """Signed with a different key. The signature is the whole of what a token is worth."""
    forged = security.TokenCodec("a-key-this-process-has-never-seen-abcdef").issue_access(
        security.Principal(
            subject="UNI-LASU",
            login_id="UNI-LASU",
            role=security.Role.UNIVERSITY,
            scope_kind=security.ScopeKind.UNIVERSITY,
            scope_id="UNI-LASU",
        )
    )
    response = await anonymous_client.get(
        f"{api}/auth/me", headers={"Authorization": f"Bearer {forged}"}
    )
    assert response.status_code == 401, response.text


async def test_the_public_application_form_needs_no_token(
    anonymous_client: AsyncClient, api: str
) -> None:
    """It must not 401. What it answers instead is Admissions' business, not the guard's.

    Asserting "anything but 401 or 403" rather than a success, because a well-formed application
    for a programme this test never created is legitimately a 404 — and pinning the status here
    would make this a test of Admissions that fails when Admissions changes.
    """
    response = await anonymous_client.post(
        f"{api}/admissions/applications",
        json={
            "applicant_id": "app-1",
            "program_id": "prog-csc",
            "session_id": "sess-2026",
            "full_name": "Ada Lovelace",
            "utme_scores": [
                {"subject": "english", "score": 70},
                {"subject": "mathematics", "score": 80},
                {"subject": "physics", "score": 65},
                {"subject": "chemistry", "score": 60},
            ],
        },
    )
    assert response.status_code not in (401, 403), response.text


# ---- tier one: the role gate ----


class TestTheRoleGate:
    async def test_a_student_may_not_create_a_faculty(
        self, anonymous_client: AsyncClient, api: str, headers
    ) -> None:
        response = await anonymous_client.post(
            f"{api}/faculty-department/faculties",
            json={"faculty_id": "fac-sci", "name": "Science", "code": "SCI"},
            headers=headers(security.Role.STUDENT, subject="stu-1"),
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"] == "ForbiddenError"

    async def test_a_department_may_not_create_a_faculty(
        self, anonymous_client: AsyncClient, api: str, headers
    ) -> None:
        """Creating a faculty is university work: a department cannot create the level above it."""
        response = await anonymous_client.post(
            f"{api}/faculty-department/faculties",
            json={"faculty_id": "fac-sci", "name": "Science", "code": "SCI"},
            headers=headers(security.Role.DEPARTMENT, subject="dept-csc"),
        )
        assert response.status_code == 403, response.text

    async def test_a_lecturer_may_not_correct_a_grade(
        self, anonymous_client: AsyncClient, api: str, headers
    ) -> None:
        """The correction is the registry overriding a submission, never the submitter redoing it.

        A lecturer who could reach this route could rewrite their own mark with no second party
        involved, which is the audit entry the aggregate demands doing nothing at all.
        """
        response = await anonymous_client.post(
            f"{api}/academic-records/records/stu-1/corrections",
            json={
                "course_id": "csc101",
                "semester_id": "sem-1",
                "score": 70,
                "reason": "marks transposed",
                "authorised_by": "lec-1",
            },
            headers=headers(security.Role.LECTURER, subject="lec-1"),
        )
        assert response.status_code == 403, response.text

    async def test_a_university_principal_may_not_submit_a_grade(
        self, anonymous_client: AsyncClient, api: str, headers
    ) -> None:
        """The one guard with no university fallback, and the omission is deliberate.

        ``GradeSubmission.submit()`` asks whether *this lecturer* is assigned to the course. A
        university principal admitted here would reach a refusal it could never satisfy, so a
        403 at the edge is the more truthful answer.
        """
        response = await anonymous_client.post(
            f"{api}/faculty-department/grade-submissions",
            json={
                "lecturer_id": "lec-1",
                "session_id": "sess-2026",
                "student_id": "stu-1",
                "course_id": "csc101",
                "semester_id": "sem-1",
                "score": 70,
            },
            headers=headers(security.Role.UNIVERSITY),
        )
        assert response.status_code == 403, response.text

    async def test_a_student_may_not_list_the_credential_roll(
        self, anonymous_client: AsyncClient, api: str, headers
    ) -> None:
        response = await anonymous_client.get(
            f"{api}/auth/credentials", headers=headers(security.Role.STUDENT, subject="stu-1")
        )
        assert response.status_code == 403, response.text


# ---- tier two: the scope gate ----


class TestTheScopeGate:
    async def test_a_faculty_officer_may_not_create_a_department_elsewhere(
        self, anonymous_client: AsyncClient, api: str, headers
    ) -> None:
        """The request names the faculty, so this is one of the checks that can be made honestly."""
        response = await anonymous_client.post(
            f"{api}/faculty-department/departments",
            json={
                "department_id": "dept-mth",
                "faculty_id": "fac-arts",
                "name": "Mathematics",
                "code": "MTH",
            },
            headers=headers(security.Role.FACULTY, subject="fac-sci"),
        )
        assert response.status_code == 403, response.text
        assert "fac-arts" in response.json()["detail"]

    async def test_a_department_registrar_may_not_register_a_lecturer_elsewhere(
        self, anonymous_client: AsyncClient, api: str, headers
    ) -> None:
        response = await anonymous_client.post(
            f"{api}/faculty-department/lecturers",
            json={
                "lecturer_id": "lec-9",
                "department_id": "dept-mth",
                "full_name": "Grace Hopper",
            },
            headers=headers(security.Role.DEPARTMENT, subject="dept-csc"),
        )
        assert response.status_code == 403, response.text

    async def test_a_student_may_not_read_another_students_record(
        self, anonymous_client: AsyncClient, api: str, headers
    ) -> None:
        response = await anonymous_client.get(
            f"{api}/academic-records/records/stu-2",
            headers=headers(security.Role.STUDENT, subject="stu-1"),
        )
        assert response.status_code == 403, response.text

    async def test_a_student_may_not_read_another_students_ledger(
        self, anonymous_client: AsyncClient, api: str, headers
    ) -> None:
        response = await anonymous_client.get(
            f"{api}/billing/accounts/stu-2",
            headers=headers(security.Role.STUDENT, subject="stu-1"),
        )
        assert response.status_code == 403, response.text

    async def test_a_student_may_not_register_somebody_else_for_a_course(
        self, anonymous_client: AsyncClient, api: str, headers
    ) -> None:
        response = await anonymous_client.post(
            f"{api}/enrollment/registrations",
            json={
                "enrollment_id": "enr-1",
                "student_id": "stu-2",
                "course_id": "csc101",
                "session_id": "sess-2026",
                "semester_id": "sem-1",
                "semester_ordinal": 1,
            },
            headers=headers(security.Role.STUDENT, subject="stu-1"),
        )
        assert response.status_code == 403, response.text

    async def test_a_student_reaches_their_own_things_by_either_of_their_names(
        self, anonymous_client: AsyncClient, api: str, headers
    ) -> None:
        """A student's login id is their matric number and their subject is the ``student_id``.

        Both must work, because which one a URL carries depends on the route: the bursary quotes
        a matric number, this system's own ids are ``stu-*``, and a student holds both. Neither
        request finds anything here — nothing was seeded — and that is the point: what is being
        asserted is that the *guard* let them through, so anything but a 403 passes.
        """
        by_subject = await anonymous_client.get(
            f"{api}/academic-records/records/stu-1",
            headers=headers(security.Role.STUDENT, subject="stu-1", login_id="260591001"),
        )
        by_matric = await anonymous_client.get(
            f"{api}/billing/accounts/260591001",
            headers=headers(security.Role.STUDENT, subject="stu-1", login_id="260591001"),
        )
        assert by_subject.status_code != 403, by_subject.text
        assert by_matric.status_code != 403, by_matric.text

    async def test_the_university_passes_every_scope_check(
        self, anonymous_client: AsyncClient, api: str, headers
    ) -> None:
        """What university-scoped means, asserted rather than assumed."""
        response = await anonymous_client.post(
            f"{api}/faculty-department/departments",
            json={
                "department_id": "dept-mth",
                "faculty_id": "fac-anything",
                "name": "Mathematics",
                "code": "MTH",
            },
            headers=headers(security.Role.UNIVERSITY),
        )
        assert response.status_code != 403, response.text
