"""The login surface, driven end to end through the real application.

This is the one module that goes through ``POST /auth/login`` with a real password against a
real stored credential. Everything else in ``tests/http/`` mints a token from the app's codec
instead — see ``conftest.access_token`` on why forty route tests should not be coupled to the
password path.
"""

import pytest
from httpx import AsyncClient

import security
from identity.adapters.inbound.http.router import REFRESH_COOKIE
from identity.domain.credential import Credential
from identity.domain.values import Role

PASSWORD = "correct-horse-battery"


@pytest.fixture
async def seeded(repos):
    """One credential of each kind, stored the way the seeder stores them."""
    credentials = repos.credentials()
    for login_id, principal_id, role in (
        ("UNI-LASU", "UNI-LASU", Role.UNIVERSITY),
        ("FAC-SCI", "FAC-SCI", Role.FACULTY),
        ("DEPT-CSC", "DEPT-CSC", Role.DEPARTMENT),
        ("LEC-0001", "LEC-0001", Role.LECTURER),
        ("260591001", "stu-1", Role.STUDENT),
    ):
        await credentials.add(
            Credential.issue(
                credential_id=f"CRED-{principal_id}",
                login_id=login_id,
                principal_id=principal_id,
                role=role,
                scope_unit_id=principal_id,
                password=PASSWORD,
            )
        )
    return credentials


async def login(client: AsyncClient, api: str, login_id: str, password: str = PASSWORD):
    return await client.post(f"{api}/auth/login", json={"login_id": login_id, "password": password})


class TestLoggingIn:
    @pytest.mark.parametrize(
        "login_id,role,principal_id",
        [
            ("UNI-LASU", "university", "UNI-LASU"),
            ("FAC-SCI", "faculty", "FAC-SCI"),
            ("DEPT-CSC", "department", "DEPT-CSC"),
            ("LEC-0001", "lecturer", "LEC-0001"),
            ("260591001", "student", "stu-1"),
        ],
    )
    async def test_each_level_logs_in_with_its_own_id(
        self, anonymous_client, api, seeded, login_id, role, principal_id
    ) -> None:
        """The five principals ``auth.md`` confirms, each reaching a session of its own."""
        response = await login(anonymous_client, api, login_id)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["principal"] == {
            "principal_id": principal_id,
            "login_id": login_id,
            "role": role,
            "scope_kind": role,
            "scope_id": principal_id,
            "is_active": True,
        }

    async def test_a_student_logs_in_with_their_matric_number(
        self, anonymous_client, api, seeded
    ) -> None:
        """Confirmed: the number they are given is the number they type."""
        assert (await login(anonymous_client, api, "260591001")).status_code == 200
        assert (await login(anonymous_client, api, "stu-1")).status_code == 401

    async def test_the_access_token_opens_a_guarded_route(
        self, anonymous_client, api, seeded
    ) -> None:
        """The whole point, asserted once: a password in, and a route that was 401 answers."""
        token = (await login(anonymous_client, api, "UNI-LASU")).json()["access_token"]
        response = await anonymous_client.get(
            f"{api}/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["login_id"] == "UNI-LASU"

    async def test_the_refresh_token_is_an_httponly_cookie_and_not_in_the_body(
        self, anonymous_client, api, seeded
    ) -> None:
        """Its whole protection against a script on the page is that JavaScript cannot read it.

        Returning it in the body as well would hand it to exactly the code the flag excludes.
        """
        response = await login(anonymous_client, api, "UNI-LASU")
        assert "refresh_token" not in response.json()
        cookie = response.headers["set-cookie"]
        assert REFRESH_COOKIE in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie

    async def test_the_refresh_cookie_is_not_secure_against_a_plain_http_frontend(
        self, anonymous_client, api, seeded
    ) -> None:
        """``ALLOWED_ORIGINS`` here is ``http://localhost:3000``, so ``Secure`` is off.

        A ``Secure`` cookie is never sent to an ``http://`` origin, so with the flag on a
        developer could not stay logged in. Deriving it from the origins rather than from a
        switch means the insecure case is exactly the case where the frontend is already
        insecure — see ``main._cookies_require_https``.
        """
        response = await login(anonymous_client, api, "UNI-LASU")
        assert "Secure" not in response.headers["set-cookie"]

    async def test_no_password_hash_ever_crosses_the_wire(
        self, anonymous_client, api, seeded
    ) -> None:
        response = await login(anonymous_client, api, "UNI-LASU")
        assert "scrypt" not in response.text
        assert "password" not in response.text


class TestBeingRefused:
    async def test_a_wrong_password_is_a_401(self, anonymous_client, api, seeded) -> None:
        assert (await login(anonymous_client, api, "UNI-LASU", "wrong")).status_code == 401

    async def test_an_unknown_login_id_is_a_401(self, anonymous_client, api, seeded) -> None:
        assert (await login(anonymous_client, api, "nobody-at-all")).status_code == 401

    async def test_the_two_refusals_are_indistinguishable(
        self, anonymous_client, api, seeded
    ) -> None:
        """The property that stops somebody enumerating the university's roll.

        Login ids here are matric numbers and department codes, both guessable in bulk. An
        endpoint that answered differently for "no such account" and "wrong password" would let
        an attacker sort the guesses into real and unreal without ever getting in.
        """
        unknown = await login(anonymous_client, api, "nobody-at-all")
        wrong = await login(anonymous_client, api, "UNI-LASU", "wrong")
        assert unknown.status_code == wrong.status_code
        assert unknown.json() == wrong.json()

    async def test_a_deactivated_credential_is_refused_the_same_way(
        self, anonymous_client, api, seeded
    ) -> None:
        credential = await seeded.find_by_login_id("LEC-0001")
        credential.deactivate()
        await seeded.save(credential)

        refused = await login(anonymous_client, api, "LEC-0001")
        assert refused.status_code == 401
        assert refused.json() == (await login(anonymous_client, api, "nobody")).json()


class TestRefreshing:
    async def test_the_cookie_buys_a_new_access_token(self, anonymous_client, api, seeded) -> None:
        await login(anonymous_client, api, "DEPT-CSC")
        response = await anonymous_client.post(f"{api}/auth/refresh")
        assert response.status_code == 200, response.text
        assert response.json()["principal"]["login_id"] == "DEPT-CSC"

    async def test_refreshing_does_not_rotate_the_cookie(
        self, anonymous_client, api, seeded
    ) -> None:
        """Not an omission. Re-stamping the cookie on every page load would turn a 12-hour
        window into one that never closes, and there is no server-side record against which a
        rotated token could be checked."""
        await login(anonymous_client, api, "DEPT-CSC")
        response = await anonymous_client.post(f"{api}/auth/refresh")
        assert "set-cookie" not in response.headers

    async def test_refreshing_without_a_cookie_is_a_401(
        self, anonymous_client, api, seeded
    ) -> None:
        assert (await anonymous_client.post(f"{api}/auth/refresh")).status_code == 401

    async def test_a_credential_deactivated_since_login_cannot_refresh(
        self, anonymous_client, api, seeded
    ) -> None:
        """The credential is re-read from storage rather than trusted out of the token.

        This is the closest thing to revocation the system has, and its bound is one
        access-token lifetime rather than twelve hours.
        """
        await login(anonymous_client, api, "DEPT-CSC")
        credential = await seeded.find_by_login_id("DEPT-CSC")
        credential.deactivate()
        await seeded.save(credential)

        assert (await anonymous_client.post(f"{api}/auth/refresh")).status_code == 401

    async def test_an_access_token_is_not_accepted_as_a_refresh_token(
        self, anonymous_client, api, seeded
    ) -> None:
        access = (await login(anonymous_client, api, "UNI-LASU")).json()["access_token"]
        anonymous_client.cookies.set(REFRESH_COOKIE, access)
        assert (await anonymous_client.post(f"{api}/auth/refresh")).status_code == 401

    async def test_logging_out_clears_the_cookie(self, anonymous_client, api, seeded) -> None:
        await login(anonymous_client, api, "UNI-LASU")
        response = await anonymous_client.post(f"{api}/auth/logout")
        assert response.status_code == 204
        assert (await anonymous_client.post(f"{api}/auth/refresh")).status_code == 401


class TestChangingYourOwnPassword:
    async def test_a_principal_changes_their_own(self, anonymous_client, api, seeded) -> None:
        token = (await login(anonymous_client, api, "LEC-0001")).json()["access_token"]
        response = await anonymous_client.post(
            f"{api}/auth/me/password",
            json={"current_password": PASSWORD, "new_password": "a-brand-new-password"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        assert (await login(anonymous_client, api, "LEC-0001")).status_code == 401
        assert (
            await login(anonymous_client, api, "LEC-0001", "a-brand-new-password")
        ).status_code == 200

    async def test_the_old_password_must_be_right(self, anonymous_client, api, seeded) -> None:
        token = (await login(anonymous_client, api, "LEC-0001")).json()["access_token"]
        response = await anonymous_client.post(
            f"{api}/auth/me/password",
            json={"current_password": "not-it", "new_password": "a-brand-new-password"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422, response.text
        assert (await login(anonymous_client, api, "LEC-0001")).status_code == 200

    async def test_a_password_below_the_floor_is_refused_by_the_domain(
        self, anonymous_client, api, seeded
    ) -> None:
        """No ``min_length`` in the schema: the floor lives in ``PasswordHash.of`` and rule (d)
        forbids the route from naming it. It surfaces as a 422 either way."""
        token = (await login(anonymous_client, api, "LEC-0001")).json()["access_token"]
        response = await anonymous_client.post(
            f"{api}/auth/me/password",
            json={"current_password": PASSWORD, "new_password": "short"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422, response.text

    async def test_the_route_takes_no_login_id_at_all(self, anonymous_client, api, seeded) -> None:
        """The security property of this route: whose password changes comes from the token.

        A body that could name somebody else would make this an administrative reset that any
        valid token could reach, with ``current_password`` the only thing in the way.
        """
        token = (await login(anonymous_client, api, "LEC-0001")).json()["access_token"]
        response = await anonymous_client.post(
            f"{api}/auth/me/password",
            json={
                "login_id": "UNI-LASU",
                "current_password": PASSWORD,
                "new_password": "a-brand-new-password",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422, response.text
        assert (await login(anonymous_client, api, "UNI-LASU")).status_code == 200


class TestAdministeringCredentials:
    async def test_the_university_issues_a_credential_that_then_works(
        self, anonymous_client, api, seeded
    ) -> None:
        token = (await login(anonymous_client, api, "UNI-LASU")).json()["access_token"]
        created = await anonymous_client.post(
            f"{api}/auth/credentials",
            json={
                "login_id": "260591002",
                "principal_id": "stu-2",
                "role": "student",
                "password": "another-good-password",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert created.status_code == 201, created.text
        assert (
            await login(anonymous_client, api, "260591002", "another-good-password")
        ).status_code == 200

    async def test_a_duplicate_login_id_is_a_409(self, anonymous_client, api, seeded) -> None:
        token = (await login(anonymous_client, api, "UNI-LASU")).json()["access_token"]
        response = await anonymous_client.post(
            f"{api}/auth/credentials",
            json={
                "login_id": "DEPT-CSC",
                "principal_id": "somebody-else",
                "role": "department",
                "password": "another-good-password",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409, response.text

    async def test_a_second_credential_for_one_principal_is_a_409(
        self, anonymous_client, api, seeded
    ) -> None:
        """Two live passwords for one person, with no way to tell which they use."""
        token = (await login(anonymous_client, api, "UNI-LASU")).json()["access_token"]
        response = await anonymous_client.post(
            f"{api}/auth/credentials",
            json={
                "login_id": "LEC-0001-again",
                "principal_id": "LEC-0001",
                "role": "lecturer",
                "password": "another-good-password",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409, response.text

    async def test_a_role_this_system_does_not_have_is_a_422(
        self, anonymous_client, api, seeded
    ) -> None:
        token = (await login(anonymous_client, api, "UNI-LASU")).json()["access_token"]
        response = await anonymous_client.post(
            f"{api}/auth/credentials",
            json={
                "login_id": "chancellor",
                "principal_id": "chancellor",
                "role": "chancellor",
                "password": "another-good-password",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422, response.text
        assert "university" in response.json()["detail"]

    async def test_deactivating_a_credential_stops_it_logging_in(
        self, anonymous_client, api, seeded
    ) -> None:
        token = (await login(anonymous_client, api, "UNI-LASU")).json()["access_token"]
        response = await anonymous_client.put(
            f"{api}/auth/credentials/LEC-0001/active",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        assert (await login(anonymous_client, api, "LEC-0001")).status_code == 401

    async def test_the_roll_carries_no_hashes(self, anonymous_client, api, seeded) -> None:
        token = (await login(anonymous_client, api, "UNI-LASU")).json()["access_token"]
        response = await anonymous_client.get(
            f"{api}/auth/credentials", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, response.text
        assert len(response.json()) == 5
        assert "scrypt" not in response.text


class TestTheCodecTheAppWiredIsTheOneItVerifiesWith:
    async def test_a_token_from_login_is_verified_by_the_guards(
        self, anonymous_client, api, seeded, app
    ) -> None:
        """Two codecs would be two keys, and every token this process issued would be refused.

        Asserted by decoding a login's token with the codec the guards use, rather than by
        trusting that ``build()`` passed the same object twice.
        """
        token = (await login(anonymous_client, api, "DEPT-CSC")).json()["access_token"]
        principal = getattr(app.state, security.STATE_KEY).decode(token)
        assert principal.role is security.Role.DEPARTMENT
        assert principal.scope_id == "DEPT-CSC"
