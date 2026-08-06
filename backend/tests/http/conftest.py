"""Wiring for the HTTP tests: the real application, over whichever persistence is selected.

This suite does something none of the others do — it builds the **whole system**. Every other
conftest wires one context; ``src/main.py`` wires all eight, and these tests drive it through
an ASGI transport rather than calling use cases directly. What that buys is the only check that
the composition root is right: a router pointed at the wrong container, a Protocol satisfied by
an object with the wrong method name, or a subscription never made are all invisible to a
per-context test and fatal in production.

It runs on both backends for free, because ``build()`` asks for repositories by name and the
``adapters`` fixture already resolves that against ``UMS_TEST_BACKEND``. The app under test is
therefore the same object uvicorn serves, minus only the engine and the environment.

``lifespan`` is deliberately *not* run. It would build a Postgres engine from ``DATABASE_URL``
and rebuild every repository, discarding the ones the fixture just chose. ``build()`` is called
directly instead, which is the same function the lifespan calls.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from tests.conftest import Adapters

import main

WEBHOOK_SECRET = "sk_test_not_a_real_key"
"""The same fixture secret ``tests/billing/conftest.py`` uses, for the same reason.

The real key is rotated and lives in the environment; that a test can pick its own is the whole
benefit of the secret being a constructor argument rather than something ``src/`` reads.
"""

JWT_SECRET = "a-test-signing-key-long-enough-for-hs256"
"""Its own key, for ``WEBHOOK_SECRET``'s reason: the real one is rotated and lives in the
environment, and that a test can pick its own is the whole benefit of it being a constructor
argument rather than something ``src/`` reads."""

DEPARTMENT_NUMERIC_CODES = '{"CSC": "0591"}'
"""One department, enough to issue a matric number.

The register is configuration with no default — see
``FacultyDepartmentDepartmentCodeAdapter`` on why guessing it would be worse than not having
it — so a test that wants to register a student has to state one, and this is that statement.
"""


@pytest.fixture
def settings() -> main.Settings:
    """Settings with nothing real in them.

    ``DATABASE_URL`` is never dialled — see this module's docstring on the skipped lifespan.
    """
    return main.Settings(
        {
            "DATABASE_URL": "postgresql+asyncpg://unused:unused@localhost:5432/unused",
            "PAYSTACK_SECRET_KEY": WEBHOOK_SECRET,
            "JWT_SECRET_KEY": JWT_SECRET,
            "ALLOWED_ORIGINS": '["http://localhost:3000"]',
            "DEPARTMENT_NUMERIC_CODES": DEPARTMENT_NUMERIC_CODES,
        }
    )


class Repositories:
    """``Adapters``, memoised, so a test can reach the objects the app was built with.

    ``Adapters`` builds a fresh repository per call, which is right for a per-context conftest
    asking once. Here the app asks once and the *test* needs the same instance back — to seat a
    course offering, open a session, or assign a lecturer, none of which has a use case in front
    of it and therefore none of which can be done over HTTP.

    Memoising is also what makes the in-memory run meaningful: two instances of an in-memory
    repository are two separate stores, so without this a test would seed one and the app would
    read the other and find nothing.
    """

    def __init__(self, adapters: Adapters) -> None:
        self._adapters = adapters
        self._built: dict[str, object] = {}

    def __getattr__(self, name: str):
        factory = getattr(self._adapters, name)

        def build_once():
            if name not in self._built:
                self._built[name] = factory()
            return self._built[name]

        return build_once


@pytest.fixture
def repos(adapters: Adapters) -> Repositories:
    """The repositories the app is wired with, reachable for seeding."""
    return Repositories(adapters)


@pytest.fixture
def app(repos: Repositories, settings: main.Settings):
    """The real application, wired against the selected persistence."""
    application = main.create_app(settings)
    main.build(application, repos, settings)
    return application


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    """An HTTP client speaking to the app in-process, with no socket and no server."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://ums.test"
    ) as http_client:
        yield http_client


@pytest.fixture
def api() -> str:
    """The version prefix, in one place, so a bump is one edit."""
    return main.API_PREFIX


def api_routes(app) -> list[APIRoute]:
    """Every mounted route, flattened.

    ``app.routes`` is not a flat list of routes: ``include_router`` leaves an ``_IncludedRouter``
    holding the real ones, so iterating the top level finds one route and misses twenty-three.
    A test that filtered ``isinstance(route, APIRoute)`` over the top level would pass while
    checking almost nothing, which is exactly what happened here before this existed.
    """
    found: list[APIRoute] = []
    pending = list(app.routes)
    while pending:
        route = pending.pop()
        if isinstance(route, APIRoute):
            found.append(route)
        elif hasattr(route, "original_router"):
            pending.extend(route.original_router.routes)
        elif hasattr(route, "routes"):
            pending.extend(route.routes)
    return found
