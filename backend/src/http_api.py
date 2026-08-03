"""The part of the HTTP adapters that has no bounded context in it.

The error envelope, the machinery that turns a context's exception vocabulary into status
codes, and the dependency-lookup helper every router uses. Whether a duplicate identifier is a
409 is a fact about HTTP, not about admissions or billing, and seven copies of that decision
would be seven chances for one of them to answer 200.

**A flat module rather than a package, for the reason ``persistence.py`` gives at length.**
``discover_contexts()`` in ``tests/architecture/test_dependency_rule.py`` finds bounded contexts
by looking for directories under ``src/`` carrying an ``__init__.py``. A package here would
become an eighth context, the fitness test's ``EXPECTED_CONTEXTS`` assertion would fail, and
every router importing it would read as a cross-context import. A module is none of those
things, and it is honest: this is transport, not a context, and it holds no domain type and no
use case.

**What it deliberately does not hold is any context's error table.** Each context maps its own
exceptions in its own ``adapters/inbound/http/errors.py``, because ``CourseNotFoundError`` is
five unrelated classes across this codebase and a central table would have to import all seven
contexts to name them — which is the thing the dependency rule exists to stop. This module
supplies the mechanism; the contexts supply the vocabulary.
"""

import json
from collections.abc import Awaitable, Callable, Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

ExceptionStatuses = Mapping[type[Exception], int]
"""A context's own exceptions, mapped to the status each should leave as."""


class ErrorResponse(BaseModel):
    """The one error shape this API ever returns.

    ``error`` is the exception's class name, which is stable, greppable and the thing a client
    writes a condition against. ``detail`` is the message the domain wrote, which is prose meant
    for a person and may change without notice. A client keying off ``detail`` has coupled
    itself to a sentence; the split is there so it does not have to.
    """

    error: str = Field(description="The exception class name, e.g. 'CourseNotFoundError'.")
    detail: str = Field(description="Human-readable explanation. Not a stable interface.")


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """The ``responses=`` argument documenting which errors a route can produce.

    Purely for the OpenAPI schema: without it every route advertises a 200 and FastAPI's own
    422, and a client generator has no idea a 409 is possible.
    """
    return {status: {"model": ErrorResponse} for status in sorted(set(statuses))}


def _status_for(exc: Exception, statuses: ExceptionStatuses) -> int | None:
    """The status mapped to ``exc``, matching the most specific class first.

    Walking the MRO rather than looking up ``type(exc)`` is what lets a context map its base
    error to 422 and a handful of subclasses to 404 without restating the base for each. Order
    matters and the MRO already has it: the first ancestor with an entry wins, so a subclass
    always beats the base it inherits from.
    """
    for ancestor in type(exc).__mro__:
        if ancestor in statuses:
            return statuses[ancestor]
    return None


def install_exception_handlers(app: FastAPI, statuses: ExceptionStatuses) -> None:
    """Register one handler per mapped exception, all of them answering in ``ErrorResponse``.

    Registered per class rather than as a single catch-all on ``Exception``: a blanket handler
    would swallow the errors nobody has classified, and an unmapped exception *should* reach
    the server's 500 path, where it is logged as the bug it is rather than reported to a client
    as a tidy 400. That is the same argument ``persistence.classify`` makes about unrecognised
    SQLSTATEs — a failure nobody has classified is a failure nobody has established is safe to
    paper over.
    """
    handle = _handler_for(statuses)
    for exception_type in statuses:
        app.add_exception_handler(exception_type, handle)


def install_envelope_for_framework_errors(app: FastAPI) -> None:
    """Make FastAPI's own refusals answer in :class:`ErrorResponse` like everything else.

    Without this an API has two error shapes: ``{"error", "detail"}`` from the contexts and
    ``{"detail"}`` from the framework's 404s, 405s and validation failures. A client would have
    to parse both and could not tell from the status which it was about to get. One shape is
    worth the two handlers.

    Validation failures keep the framework's structured report as the ``detail``, serialised —
    it says which field of which body was wrong, which is the only genuinely useful thing about
    a 422 and not something to flatten into a sentence.
    """

    async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, StarletteHTTPException)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=HTTPStatus(exc.status_code).phrase.replace(" ", "") + "Error",
                detail=str(exc.detail),
            ).model_dump(),
            headers=getattr(exc, "headers", None),
        )

    async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, RequestValidationError)
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="RequestValidationError",
                detail=json.dumps(jsonable_encoder(exc.errors())),
            ).model_dump(),
        )

    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)


def _handler_for(
    statuses: ExceptionStatuses,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        status = _status_for(exc, statuses)
        if status is None:  # pragma: no cover - only reachable by a mis-registered handler
            raise exc
        return JSONResponse(
            status_code=status,
            content=ErrorResponse(error=type(exc).__name__, detail=str(exc)).model_dump(),
        )

    return handle


def dependencies_of[T](request: Request, key: str, expected: type[T]) -> T:
    """The use cases a router was wired with, off ``app.state``.

    Routers reach their use cases through this rather than importing the composition root, which
    would be a cycle: the root imports every router to mount it. ``app.state`` is the handover
    point, and the key is a constant each context owns.

    The type check is not ceremony. A router wired against the wrong context's container would
    otherwise fail at the first attribute access, inside a request, as an ``AttributeError`` that
    reads like a missing field rather than like a wiring mistake.
    """
    container = getattr(request.app.state, key, None)
    if container is None:
        raise RuntimeError(
            f"nothing is wired at app.state.{key}; the composition root has not run, or this "
            f"router was mounted on an app that does not serve {expected.__name__}"
        )
    if not isinstance(container, expected):
        raise RuntimeError(
            f"app.state.{key} holds {type(container).__name__}, not {expected.__name__}"
        )
    return container
