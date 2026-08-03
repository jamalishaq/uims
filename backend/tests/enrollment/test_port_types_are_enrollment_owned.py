"""Every type crossing an Enrollment port is Enrollment's own.

The build playbook's verification for this phase asks for two things: that the ports return
Enrollment's own types, and that nothing imports another context's domain. The second is
already enforced globally by ``tests/architecture/test_dependency_rule.py`` and stays the
merge gate.

This module does the first, and it is the stronger check of the two. A signature naming a
foreign type would fail the import rule too — but only because the import is visible.
What this catches is the subtler drift: a port that starts answering in dictionaries, or in
strings shaped like another context's ids, or in a type that quietly moved out of
``domain/``. Those all pass an import check and all mean the same thing — that Enrollment
has begun taking its vocabulary from somewhere else.

The rule is: every parameter and return annotation on every port method resolves to a type
defined under ``enrollment.domain``, or to a builtin. Not ``enrollment.ports`` — a fact
object defined beside the port could not be read by the domain layer, which may not import
outward, and would have to be translated a second time on the way in.
"""

import inspect
import types
import typing

import pytest

from enrollment.ports import (
    CourseInfoPort,
    CourseOfferingRepositoryPort,
    EnrollmentRepositoryPort,
    FinancialClearancePort,
    StudentAcademicStandingPort,
)

PORTS = [
    CourseInfoPort,
    CourseOfferingRepositoryPort,
    EnrollmentRepositoryPort,
    FinancialClearancePort,
    StudentAcademicStandingPort,
]

QUERY_PORTS = [CourseInfoPort, StudentAcademicStandingPort, FinancialClearancePort]
"""The three that reach into other contexts (CLAUDE.md section 3). The others are our own."""


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
    return module.startswith("enrollment.domain") or module == "builtins"


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
        f"\n{len(foreign)} type(s) crossing an Enrollment port are not Enrollment's:\n"
        + "\n".join(foreign)
    )


@pytest.mark.parametrize("port", QUERY_PORTS, ids=lambda port: port.__name__)
def test_a_query_port_answers_facts_and_never_a_decision(port: type) -> None:
    """No port method is named for a judgement Enrollment is supposed to make itself.

    ``is_cleared_for_registration`` is the one boolean allowed across a boundary, and it is
    Billing's own rule about its own ledger (CLAUDE.md section 3). What must never appear is
    a port asked whether a student may register, whether a prerequisite is satisfied, or
    whether a course has room — those are ``EligibilityRule``'s, and a port that answered
    one would have moved the judgment out of this context.
    """
    forbidden = ("eligible", "may_register", "can_register", "prerequisites_met", "has_capacity")
    named = [
        name
        for name, _ in inspect.getmembers(port, predicate=inspect.isfunction)
        if not name.startswith("_") and any(word in name for word in forbidden)
    ]
    assert not named, f"{port.__name__} asks another context to make Enrollment's judgment: {named}"


def test_the_ports_module_declares_no_schedule_port() -> None:
    """Model A is permanent (CLAUDE.md section 3): registration is schedule-blind.

    Adding one would be a design change requiring escalation, never a feature addition —
    which is exactly the kind of thing that arrives as a well-meaning commit, so it is
    asserted rather than trusted.
    """
    import enrollment.ports

    assert not [name for name in enrollment.ports.__all__ if "schedule" in name.lower()]
    assert not [name for name in enrollment.ports.__all__ if "timetable" in name.lower()]
