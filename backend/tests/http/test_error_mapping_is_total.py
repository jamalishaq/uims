"""Every error a context can raise has a status, and no error falls through to a 500.

There are twenty-four ``errors.py`` modules in this codebase and no shared base class between
them: ``ApplicationError`` names five unrelated classes, ``MissingIdentifierError`` names six.
A table written by hand against that will eventually miss one, and the way it will be noticed
is a stack trace in production where a 422 was meant.

So the table is checked rather than trusted. This walks the real modules, finds every exception
class each context defines, and asserts the context's own table resolves it — by the same MRO
walk ``http_api`` uses at request time, so what is asserted here is exactly what happens then.

Deliberately *not* a check that every class is listed explicitly: a base mapped to 422 covers
its subclasses, which is the whole point of matching along the MRO. What must not exist is an
error with no ancestor in the table at all.
"""

import importlib
import inspect
import pkgutil

import pytest

from http_api import ExceptionStatuses, _status_for

CONTEXTS = (
    "academic_records",
    "admissions",
    "billing",
    "course_catalog",
    "enrollment",
    "faculty_department",
    "identity",
    "student_profile",
)

PERMITTED_STATUSES = frozenset({400, 401, 403, 404, 409, 422, 500, 502, 503})
"""What a context is allowed to map to. A typo'd 4004 would otherwise sail through."""


def _statuses_for(context: str) -> ExceptionStatuses:
    module = importlib.import_module(f"{context}.adapters.inbound.http")
    return module.EXCEPTION_STATUSES


def _error_classes(context: str) -> list[type[Exception]]:
    """Every exception class the context defines, across all three of its ``errors.py``.

    Found by import rather than by parsing, because what matters is the class object the MRO
    walk will see at runtime, not the name in the source.
    """
    package = importlib.import_module(context)
    found: dict[str, type[Exception]] = {}
    for module_info in pkgutil.walk_packages(package.__path__, prefix=f"{context}."):
        if not module_info.name.endswith(".errors"):
            continue
        if ".adapters." in module_info.name:
            continue  # the http table itself, and the postgres translation helpers
        module = importlib.import_module(module_info.name)
        for name, obj in vars(module).items():
            if (
                inspect.isclass(obj)
                and issubclass(obj, Exception)
                and obj.__module__ == module.__name__
            ):
                found[name] = obj
    return sorted(found.values(), key=lambda cls: cls.__name__)


@pytest.mark.parametrize("context", CONTEXTS)
def test_the_context_defines_errors_at_all(context: str) -> None:
    """Guard: a wrong module path would make the check below pass vacuously, forever."""
    assert _error_classes(context), f"found no error classes under {context}"


@pytest.mark.parametrize("context", CONTEXTS)
def test_every_error_a_context_defines_resolves_to_a_status(context: str) -> None:
    statuses = _statuses_for(context)
    unmapped = [
        cls.__name__
        for cls in _error_classes(context)
        if _status_for(cls("checking"), statuses) is None
    ]
    assert unmapped == [], (
        f"{context} can raise these with no status mapped, so they would surface as a 500: "
        f"{', '.join(unmapped)}"
    )


@pytest.mark.parametrize("context", CONTEXTS)
def test_every_mapped_status_is_one_a_client_can_act_on(context: str) -> None:
    statuses = _statuses_for(context)
    assert set(statuses.values()) <= PERMITTED_STATUSES


@pytest.mark.parametrize("context", CONTEXTS)
def test_a_context_maps_only_its_own_exceptions(context: str) -> None:
    """A table naming another context's error would be a cross-context import wearing a hat.

    Rule (b) would catch the import, but only if the class were named directly; this catches
    the case where it arrived through a re-export.
    """
    foreign = [
        cls.__name__
        for cls in _statuses_for(context)
        if not cls.__module__.startswith(f"{context}.")
    ]
    assert foreign == []


def test_the_mro_walk_prefers_the_most_specific_entry() -> None:
    """The property the tables depend on: a subclass beats the base it inherits from."""

    class BaseError(Exception):
        pass

    class SpecificError(BaseError):
        pass

    statuses: ExceptionStatuses = {SpecificError: 404, BaseError: 422}
    assert _status_for(SpecificError("x"), statuses) == 404
    assert _status_for(BaseError("x"), statuses) == 422
