"""Every type crossing an Academic Records port is Academic Records' own.

The same check Enrollment carries, applied here for a sharper reason. This context has
exactly one query port — ``CourseCreditPort`` into Course Catalog — and it is a *new*
cross-context dependency, added in Phase 4.2 after being escalated and confirmed rather
than inferred. A single narrow port is easy to widen by accident: a title here for a
transcript heading, a prerequisite list there for a graduation audit, and it has become a
second copy of the catalog.

``tests/architecture/test_dependency_rule.py`` already catches a foreign *import* and stays
the merge gate. What this module catches is the subtler drift, which passes an import check:
a port that starts answering in dictionaries, in strings shaped like another context's ids,
or in a type that has quietly moved out of ``domain/``.

The rule is: every parameter and return annotation on every port method resolves to a type
defined under ``academic_records.domain``, or to a builtin. Not ``academic_records.ports`` —
a fact object defined beside the port could not be read by the domain layer, which may not
import outward, and would have to be translated a second time on the way in.
"""

import inspect
import types
import typing

import pytest

from academic_records.ports import AcademicRecordRepositoryPort, CourseCreditPort

PORTS = [AcademicRecordRepositoryPort, CourseCreditPort]

QUERY_PORTS = [CourseCreditPort]
"""The one that reaches into another context. The repository is our own."""


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
    return module.startswith("academic_records.domain") or module == "builtins"


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
        f"\n{len(foreign)} type(s) crossing an Academic Records port are not this context's:\n"
        + "\n".join(foreign)
    )


@pytest.mark.parametrize("port", QUERY_PORTS, ids=lambda port: port.__name__)
def test_a_query_port_answers_facts_and_never_a_decision(port: type) -> None:
    """No port method is named for a judgement this context is supposed to make itself.

    What a mark is worth, whether it is a pass, whether a CGPA means probation: all of it is
    this context's, and a port that answered one would have moved the judgment out. Course
    Catalog is asked what a course is worth and nothing else.
    """
    forbidden = ("passed", "grade", "gpa", "cgpa", "standing", "probation", "eligible")
    named = [
        name
        for name, _ in inspect.getmembers(port, predicate=inspect.isfunction)
        if not name.startswith("_") and any(word in name for word in forbidden)
    ]
    assert not named, (
        f"{port.__name__} asks another context to make Academic Records' judgment: {named}"
    )


def test_the_ports_module_declares_no_port_into_enrollment() -> None:
    """CLAUDE.md section 3: Academic Records never queries Enrollment.

    The traffic is one-way — Enrollment reads a standing from here through its own port —
    and a port pointing back would close a loop that both contexts' docstrings promise stays
    open. Exactly the kind of thing that arrives as a well-meaning commit, so it is asserted
    rather than trusted.
    """
    import academic_records.ports

    forbidden = ("enrollment", "registration", "creditload", "credit_load", "offering")
    named = [
        name
        for name in academic_records.ports.__all__
        if any(word in name.lower() for word in forbidden)
    ]
    assert not named, f"Academic Records has acquired a port into Enrollment: {named}"


def test_the_ports_module_declares_no_event_publisher() -> None:
    """This context is the end of the chain: it consumes ``GradeSubmitted`` and announces nothing.

    Not a permanent rule the way the Enrollment one is — a transcript service or a
    graduation audit might genuinely want to hear that a grade landed. It is asserted so
    that adding one is a decision somebody makes on purpose.
    """
    import academic_records.ports

    assert not [name for name in academic_records.ports.__all__ if "publisher" in name.lower()]


def test_the_course_credit_port_asks_for_nothing_but_credits() -> None:
    """One method, one question. The narrowing is the whole design of this port."""
    methods = [
        name
        for name, _ in inspect.getmembers(CourseCreditPort, predicate=inspect.isfunction)
        if not name.startswith("_")
    ]
    assert methods == ["credits_for"]
