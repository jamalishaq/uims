"""Every type crossing a Billing port is Billing's own — and Billing queries nobody.

The same check Enrollment and Academic Records carry, applied here for a different reason.
Those two have query ports to defend against widening. This context has *none*: everything it
needs arrives as an event it consumes, and the ledger's inputs — a party, a program, a level,
a session, an amount — are held on the account rather than fetched. The property worth
asserting is that this stays true, because "Billing needs to know the student's current level,
let us add a port" is exactly the shape of a change that arrives as a well-meaning commit and
is an escalation-path decision (CLAUDE.md section 6) rather than a feature.

``tests/architecture/test_dependency_rule.py`` already catches a foreign *import* and stays the
merge gate. What this module catches is the subtler drift, which passes an import check: a port
that starts answering in dictionaries, in strings shaped like another context's ids, or in a
type that has quietly moved out of ``domain/``.

The rule is: every parameter and return annotation on every port method resolves to a type
defined under ``billing.domain``, or to a builtin. Not ``billing.ports`` — a fact object
defined beside the port could not be read by the domain layer, which may not import outward,
and would have to be translated a second time on the way in.
"""

import inspect
import types
import typing

import pytest

from billing.ports import (
    AccountRepositoryPort,
    EventPublisherPort,
    FeeScheduleRepositoryPort,
)

PORTS = [AccountRepositoryPort, EventPublisherPort, FeeScheduleRepositoryPort]


def _leaf_types(annotation: object) -> list[type]:
    """Every concrete type inside an annotation, unions, generics and ``None`` unwrapped."""
    if annotation is None or annotation is type(None):
        return []
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType) or origin in (tuple, list, frozenset, set, dict):
        return [leaf for arg in typing.get_args(annotation) for leaf in _leaf_types(arg)]
    return [annotation] if isinstance(annotation, type) else []


def _annotations_of(port: type) -> list[tuple[str, object]]:
    """Every annotated parameter and return type on every public method of ``port``."""
    annotated = []
    for name, method in inspect.getmembers(port, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        for parameter, annotation in typing.get_type_hints(method).items():
            annotated.append((f"{port.__name__}.{name}({parameter})", annotation))
    return annotated


def _is_ours(leaf: type) -> bool:
    module = getattr(leaf, "__module__", "")
    return module.startswith("billing.domain") or module == "builtins"


@pytest.mark.parametrize("port", PORTS, ids=lambda port: port.__name__)
def test_every_type_on_a_port_belongs_to_this_context(port: type) -> None:
    annotated = _annotations_of(port)
    assert annotated, f"{port.__name__} has no annotated methods — the check would pass vacuously"

    foreign = [
        f"{where}: {leaf.__module__}.{leaf.__qualname__}"
        for where, annotation in annotated
        for leaf in _leaf_types(annotation)
        if not _is_ours(leaf)
    ]
    assert not foreign, (
        f"\n{len(foreign)} type(s) crossing a Billing port are not this context's:\n"
        + "\n".join(foreign)
    )


def test_this_context_declares_no_query_port_into_any_other() -> None:
    """Billing pulls nothing from anybody. Every fact it acts on was pushed to it.

    Asserted by name because the temptation is specific and namable: a student's level, their
    program, their standing, whether they are still enrolled. Each would be a cross-context
    dependency not listed in CLAUDE.md section 3, and adding one is a decision to escalate.
    """
    import billing.ports

    forbidden = (
        "student",
        "program",
        "level",
        "course",
        "enrollment",
        "admission",
        "applicant",
        "session",
        "gateway",
    )
    named = [
        name
        for name in billing.ports.__all__
        if any(word in name.lower() for word in forbidden) and "repository" not in name.lower()
    ]
    assert not named, f"Billing has acquired a query port into another context: {named}"


def test_the_clearance_rule_is_not_declared_here() -> None:
    """``FinancialClearancePort`` is declared in *Enrollment*, in Enrollment's own language, and
    answered by an adapter (Phase 5.2). A port of that name over here would mean the consuming
    context no longer owned the interface it reads through.
    """
    import billing.ports

    assert not [name for name in billing.ports.__all__ if "clearance" in name.lower()]


def test_the_publisher_speaks_only_this_context_s_events() -> None:
    """The one port that carries a domain type outward. It carries ours."""
    hints = typing.get_type_hints(EventPublisherPort.publish)
    assert all(_is_ours(leaf) for leaf in _leaf_types(hints["event"]))
