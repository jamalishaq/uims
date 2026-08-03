"""The clearance rule is confined to one adapter, and Enrollment proper knows no arithmetic.

The build playbook's Phase 5.2 requirement was that *Enrollment code must not change at all*
when the stub is replaced, and asked for that to be asserted in the diff. A diff is a fact about
one commit; what keeps it true is the property underneath it, which is what this module checks:
the rule has exactly one home, and the layers above ``adapters/`` have no vocabulary to express
it in even if somebody wanted to.

Three rules, read off the source rather than off imports — the point is to catch a rule that
gets *restated* somewhere, which no import check would see:

(a) The clearance vocabulary is defined in exactly one module, re-exported by exactly one
    package, and named nowhere else under ``src/enrollment/``.
(b) The percentages themselves — 70 and 100 — appear nowhere inward of ``adapters/``. CLAUDE.md
    section 3 on this port: "Not one of those numbers appears in this context".
(c) Nothing under ``domain/``, ``ports/`` or ``application/`` has an *identifier* naming money:
    no ``Decimal``, no percentage, no fee, no balance. ``FinancialClearancePort`` returns a bare
    boolean precisely so that it cannot, and a caller holding an amount would eventually compare
    it to something.

Identifiers, not prose. ``financial_clearance.py``'s docstring says "nothing here returns a
balance, a percentage or an amount outstanding", and it is right to — a text search would call
that a violation and would train everyone to stop explaining themselves.

Sibling in spirit to ``test_port_types_are_enrollment_owned.py``, which guards the port's
surface where this guards what sits behind it.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "enrollment"

THE_ADAPTER = "adapters/outbound/billing_financial_clearance_adapter.py"
"""The one file allowed to hold the rule. Named here so that moving it is a deliberate act."""

THE_PACKAGE = "adapters/outbound/__init__.py"
"""Allowed to re-export the rule's names, and nothing else is. A re-export defines nothing."""

CLEARANCE_VOCABULARY = (
    "ClearanceThresholds",
    "BILLING_CLEARANCE_THRESHOLDS",
    "first_semester_percent",
    "second_semester_percent",
    "required_percent",
)

INWARD_LAYERS = ("domain", "ports", "application")

MONEY_WORDS = ("decimal", "percent", "fee", "balance", "outstanding", "money", "amount")
"""Fragments that, in an identifier inward of ``adapters/``, mean money has got past the port."""

THRESHOLD_LITERALS = frozenset({"70", "100"})


def _modules(under: str | None = None) -> list[Path]:
    root = SRC if under is None else SRC / under
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _relative(path: Path) -> str:
    return path.relative_to(SRC).as_posix()


def _identifiers(path: Path) -> set[str]:
    """Every name the module actually uses — docstrings, comments and literals excluded."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg | ast.keyword) and node.arg:
            names.add(node.arg)  # ``keyword.arg`` is ``None`` for ``**kwargs``
        elif isinstance(node, ast.alias):
            names.add(node.name.rsplit(".", maxsplit=1)[-1])
            if node.asname:
                names.add(node.asname)
        elif isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
    return names


def test_the_source_tree_was_found() -> None:
    """Guard: a wrong path would make every rule below pass vacuously, forever."""
    assert SRC.is_dir(), f"enrollment source not found at {SRC}"
    assert (SRC / THE_ADAPTER).is_file(), f"the clearance adapter is not at {THE_ADAPTER}"
    assert len(_modules()) > 10
    assert all(_modules(layer) for layer in INWARD_LAYERS)


@pytest.mark.parametrize("word", CLEARANCE_VOCABULARY)
def test_the_rule_is_named_only_where_it_is_defined_and_re_exported(word: str) -> None:
    """Two files knowing the thresholds would be two files to change when the rule changes."""
    holders = [_relative(path) for path in _modules() if word in _identifiers(path)]
    assert THE_ADAPTER in holders, f"{word!r} is not defined in {THE_ADAPTER}"
    assert set(holders) <= {THE_ADAPTER, THE_PACKAGE}, (
        f"{word!r} appears in {holders}; the clearance rule lives in {THE_ADAPTER} and nowhere "
        "else, so that changing the percentages changes one file"
    )


@pytest.mark.parametrize("layer", INWARD_LAYERS)
def test_the_percentages_appear_nowhere_inward_of_the_adapters(layer: str) -> None:
    """CLAUDE.md section 3: they are Billing policy, and Enrollment may not restate them."""
    offenders = {}
    for path in _modules(layer):
        found = {
            node.value
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.Constant) and str(node.value) in THRESHOLD_LITERALS
        }
        if found:
            offenders[_relative(path)] = sorted(map(str, found))
    assert not offenders, f"clearance percentages in {layer}/: {offenders}"


@pytest.mark.parametrize("layer", INWARD_LAYERS)
def test_no_money_identifier_reaches_the_layers_above_the_adapters(layer: str) -> None:
    """Facts in, judgment here — and a balance is not one of the facts that crosses."""
    offenders = {}
    for path in _modules(layer):
        found = sorted(
            name for name in _identifiers(path) if any(word in name.lower() for word in MONEY_WORDS)
        )
        if found:
            offenders[_relative(path)] = found
    assert not offenders, (
        f"money vocabulary in {layer}/: {offenders}. Enrollment sees a boolean; the amounts "
        f"stop at {THE_ADAPTER}."
    )


@pytest.mark.parametrize("layer", INWARD_LAYERS)
def test_nothing_inward_knows_which_implementation_it_holds(layer: str) -> None:
    """``RegisterForCourse`` takes a ``FinancialClearancePort`` and never asks which one.

    That is what let Phase 5.2 add a real adapter beside the fake without the use case, the
    eligibility rule or a single application test moving.
    """
    implementations = {"BillingFinancialClearanceAdapter", "StubFinancialClearanceAdapter"}
    for path in _modules(layer):
        named = sorted(implementations & _identifiers(path))
        assert not named, f"{_relative(path)} names {named}; it may only know the port"
