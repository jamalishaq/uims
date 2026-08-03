"""Architecture fitness test: the dependency rule.

Statically checks the import graph of ``src/`` without importing anything under test.
Four rules, per CLAUDE.md sections 3 and 4:

(a) A module under ``<context>/domain/`` imports nothing from ``application/``, ``ports/``
    or ``adapters/`` — of its own context or any other. Dependencies point inward only.
(b) A module in one context imports nothing from another context, at all. Cross-context
    access goes through query ports typed in the *consuming* context's own language, with
    anti-corruption translation in the consumer's own adapter. The composition root is the
    one named exemption — see :data:`COMPOSITION_ROOT`.
(c) A module under ``<context>/domain/`` imports no third-party package — stdlib only.
(d) A module under ``<context>/adapters/inbound/http/`` imports nothing from any ``domain/``,
    bar the one carve-out in :data:`HTTP_MAY_IMPORT_FROM_DOMAIN`. An HTTP route calls use
    cases and maps application-layer views; the Pydantic models stay on the adapter side of
    the boundary and the domain types stay on the other. Phase 6.2's verification criterion,
    made checkable.

Imports guarded by ``if TYPE_CHECKING:`` are deliberately *not* exempt: a type-only
reference across a context boundary is still a boundary violation.
"""

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"

EXPECTED_CONTEXTS = frozenset(
    {
        "academic_records",
        "admissions",
        "billing",
        "course_catalog",
        "enrollment",
        "faculty_department",
        "student_profile",
    }
)

COMPOSITION_ROOT = frozenset({"main"})
"""The one module allowed to know all seven contexts, named by exact name.

A composition root that could not import the contexts it composes would not be one. Somebody
has to introduce Faculty & Department's publisher to Billing's handler, and hand Enrollment an
adapter that reads Course Catalog, and neither context may import the other — so the job falls
to a module outside all of them. ``tests/conftest.py`` has made exactly this argument since
Phase 6.1 ("a module that imported all seven would be a module importing six contexts it has no
business knowing about. A composition root may; that is what makes it one"); this is the same
claim, now that the root has moved into ``src/`` to be served by uvicorn.

**By exact name, so the next module that wants the exemption has to argue its case** — the
arrangement ``tests/billing/test_port_types_are_billing_owned.py`` uses for
``PaymentGatewayPort``. A pattern like "any flat module" would silently admit the second
composition root, and two of them is how the wiring starts to disagree with itself.

Note this exempts *only* rule (b). ``src/main.py`` is not a context, so it has no ``domain/``
and rules (a), (c) and (d) never reach it — see :meth:`Module.layer`.
"""

DOMAIN = "domain"
OUTWARD_LAYERS = frozenset({"application", "ports", "adapters"})
HTTP_LAYER = ("adapters", "inbound", "http")
"""Where a context's HTTP routes live, relative to the context package."""

HTTP_MAY_IMPORT_FROM_DOMAIN = frozenset({"errors"})
"""The only ``domain/`` modules an HTTP adapter may name, and why it is exactly this one.

Turning a refusal into a status code is transport work — it is the definition of transport
work — and it cannot be done without naming the exceptions being turned. There is no way to
say "a ``PrerequisiteCycleError`` is a 409" without the class, and re-exporting the whole of
``domain/errors.py`` through ``application/`` to dodge the rule would be the same import
wearing a hat.

The carve-out is safe because an exception is not a model. It carries no state a route could
read, no method a route could call, and no invariant a route could break: every domain error
in this system is a bare subclass whose only payload is a message. What rule (d) exists to stop
is a route holding an *entity* — something with behaviour, that can be mutated, and whose
projection to primitives belongs in ``application/views.py``. None of that applies to a class
whose whole body is a docstring.

Narrow on purpose: one module name, not a prefix and not a pattern. ``domain.values`` is not
here, so a route still cannot reach for an enum, and ``domain.errors`` importing something
heavier later does not widen this — the rule checks what the *route* names.
"""


# ---- import graph extraction ----


@dataclass(frozen=True)
class Module:
    """A source file under ``src/``, located by context and layer."""

    path: Path
    parts: tuple[str, ...]  # dotted module parts, e.g. ("admissions", "domain", "applicant")

    @property
    def context(self) -> str:
        return self.parts[0]

    @property
    def layer(self) -> str | None:
        return self.parts[1] if len(self.parts) > 1 else None

    @property
    def is_http_adapter(self) -> bool:
        """Whether this module is one of a context's HTTP routes."""
        return self.parts[1 : 1 + len(HTTP_LAYER)] == HTTP_LAYER

    @property
    def package_parts(self) -> tuple[str, ...]:
        """The package this module lives in. For ``__init__.py`` that is the module itself."""
        return self.parts if self.path.name == "__init__.py" else self.parts[:-1]


@dataclass(frozen=True)
class ImportRef:
    """A single imported dotted name, already resolved to absolute form."""

    parts: tuple[str, ...]
    lineno: int
    text: str


def discover_contexts(src_root: Path) -> frozenset[str]:
    """Bounded contexts are the top-level packages directly under ``src/``."""
    return frozenset(
        entry.name
        for entry in src_root.iterdir()
        if entry.is_dir()
        and not entry.name.startswith((".", "__"))
        and (entry / "__init__.py").exists()
    )


def iter_modules(src_root: Path) -> list[Module]:
    modules = []
    for path in sorted(src_root.rglob("*.py")):
        parts = path.relative_to(src_root).with_suffix("").parts
        if "__pycache__" in parts:
            continue
        if path.name == "__init__.py":
            parts = parts[:-1]
        if not parts:
            continue
        modules.append(Module(path=path, parts=parts))
    return modules


def _resolve_relative(module: Module, level: int, tail: str | None) -> tuple[str, ...]:
    """Resolve ``from ..x import y`` against the importing module's own package."""
    base = module.package_parts
    ascend = level - 1
    base = base[: len(base) - ascend] if ascend <= len(base) else ()
    return (*base, *(tail.split(".") if tail else ()))


def imports_of(module: Module) -> list[ImportRef]:
    """Every dotted name imported by ``module``, as absolute parts."""
    tree = ast.parse(module.path.read_text(encoding="utf-8"), filename=str(module.path))
    refs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # `import x.y` is always absolute; there is no relative form.
            for alias in node.names:
                refs.append(
                    ImportRef(tuple(alias.name.split(".")), node.lineno, f"import {alias.name}")
                )
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = _resolve_relative(module, node.level, node.module)
                text = f"from {'.' * node.level}{node.module or ''} import ..."
            else:
                parts = tuple((node.module or "").split("."))
                text = f"from {node.module} import ..."
            if parts:
                refs.append(ImportRef(parts, node.lineno, text))
    return refs


def target_of(ref: ImportRef, contexts: frozenset[str]) -> tuple[str, str | None] | None:
    """The ``(context, layer)`` an import points at, or ``None`` if it leaves ``src/``."""
    if ref.parts[0] not in contexts:
        return None
    return ref.parts[0], (ref.parts[1] if len(ref.parts) > 1 else None)


def _where(src_root: Path, module: Module, ref: ImportRef) -> str:
    return f"{module.path.relative_to(src_root).as_posix()}:{ref.lineno}"


# ---- the four rules ----


def check_domain_is_inward_only(src_root: Path) -> list[str]:
    """(a) Nothing under ``domain/`` may reach outward to application/ports/adapters."""
    contexts = discover_contexts(src_root)
    violations = []
    for module in iter_modules(src_root):
        if module.layer != DOMAIN:
            continue
        for ref in imports_of(module):
            target = target_of(ref, contexts)
            if target and target[1] in OUTWARD_LAYERS:
                violations.append(
                    f"{_where(src_root, module, ref)}: domain module imports "
                    f"{target[0]}.{target[1]} ({ref.text}) - dependencies point inward only"
                )
    return sorted(violations)


def check_no_cross_context_imports(src_root: Path) -> list[str]:
    """(b) No module may import another context, at any layer — bar the composition root."""
    contexts = discover_contexts(src_root)
    violations = []
    for module in iter_modules(src_root):
        if module.context in COMPOSITION_ROOT:
            continue
        for ref in imports_of(module):
            target = target_of(ref, contexts)
            if target and target[0] != module.context:
                violations.append(
                    f"{_where(src_root, module, ref)}: context '{module.context}' imports "
                    f"context '{target[0]}' ({ref.text}) - cross-context access is only via "
                    f"query ports typed in the consuming context, or domain events"
                )
    return sorted(violations)


def check_domain_imports_only_stdlib(src_root: Path) -> list[str]:
    """(c) ``domain/`` may import stdlib and its own context — never a third-party package."""
    contexts = discover_contexts(src_root)
    violations = []
    for module in iter_modules(src_root):
        if module.layer != DOMAIN:
            continue
        for ref in imports_of(module):
            root = ref.parts[0]
            if root in contexts or root in sys.stdlib_module_names:
                continue
            violations.append(
                f"{_where(src_root, module, ref)}: domain module imports third-party "
                f"package '{root}' ({ref.text}) - the domain layer is stdlib-only"
            )
    return sorted(violations)


def check_http_adapters_do_not_import_domain(src_root: Path) -> list[str]:
    """(d) An HTTP route imports no domain module — its own context's least of all.

    Rule (b) already stops it reaching another context. What this adds is the *inward* half:
    a route may call use cases and read the views they return, and may not name an entity, a
    value object or a domain service. The projection from a domain type to primitives belongs
    in ``application/views.py``, inside the context that owns the vocabulary; a route that
    imported ``Course`` to build a response would be doing that translation in the transport,
    where a second transport would have to do it again and the two would drift.
    """
    contexts = discover_contexts(src_root)
    violations = []
    for module in iter_modules(src_root):
        if not module.is_http_adapter:
            continue
        for ref in imports_of(module):
            target = target_of(ref, contexts)
            if not target or target[1] != DOMAIN:
                continue
            if ref.parts[2:3] and ref.parts[2] in HTTP_MAY_IMPORT_FROM_DOMAIN:
                continue
            violations.append(
                f"{_where(src_root, module, ref)}: HTTP adapter imports "
                f"{target[0]}.{DOMAIN} ({ref.text}) - routes call use cases and map "
                f"application views; domain types stay behind the application boundary"
            )
    return sorted(violations)


def _report(violations: list[str]) -> str:
    return "\n".join(("", f"{len(violations)} dependency-rule violation(s):", *violations))


# ---- rules applied to the real source tree ----


def test_contexts_and_modules_discovered() -> None:
    """Guard: a wrong SRC path would make every rule below pass vacuously, forever."""
    assert SRC.is_dir(), f"source root not found at {SRC}"
    assert discover_contexts(SRC) == EXPECTED_CONTEXTS
    assert iter_modules(SRC), f"no modules found under {SRC}"


def test_domain_does_not_import_outward() -> None:
    violations = check_domain_is_inward_only(SRC)
    assert not violations, _report(violations)


def test_no_cross_context_imports() -> None:
    violations = check_no_cross_context_imports(SRC)
    assert not violations, _report(violations)


def test_domain_imports_only_stdlib() -> None:
    violations = check_domain_imports_only_stdlib(SRC)
    assert not violations, _report(violations)


def test_http_adapters_do_not_import_domain() -> None:
    violations = check_http_adapters_do_not_import_domain(SRC)
    assert not violations, _report(violations)


def test_the_composition_root_is_the_only_exempted_module() -> None:
    """The exemption is a name, and this is the assertion that keeps it to one.

    Rule (b) is the merge gate; an exemption widened by accident would retire it quietly.
    """
    assert frozenset({"main"}) == COMPOSITION_ROOT
    assert not COMPOSITION_ROOT & discover_contexts(SRC), (
        "the composition root may not also be a bounded context"
    )


# ---- the checkers themselves, against synthetic trees ----

CLEAN_TREE = {
    "shop/__init__.py": "",
    "shop/domain/__init__.py": "",
    "shop/domain/order.py": (
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "from decimal import Decimal\n"
        "from shop.domain.money import Money\n"
        "from .money import Money as M2\n"
    ),
    "shop/domain/money.py": "",
    "shop/application/__init__.py": "",
    "shop/application/place_order.py": "from ..domain.order import Order\nimport httpx\n",
    "shop/ports/__init__.py": "",
    "shop/adapters/__init__.py": "",
    "shop/adapters/outbound/__init__.py": "",
    "warehouse/__init__.py": "",
    "warehouse/domain/__init__.py": "",
    "warehouse/ports/__init__.py": "",
}


def _write_tree(root: Path, files: dict[str, str]) -> Path:
    src_root = root / "src"
    for relative, source in files.items():
        path = src_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return src_root


def _tree_with(root: Path, **extra: str) -> Path:
    return _write_tree(root, {**CLEAN_TREE, **extra})


def test_checker_accepts_clean_tree(tmp_path: Path) -> None:
    """The fixture itself is legal, so the negative tests below fail for the right reason."""
    src_root = _write_tree(tmp_path, CLEAN_TREE)
    assert discover_contexts(src_root) == {"shop", "warehouse"}
    assert check_domain_is_inward_only(src_root) == []
    assert check_no_cross_context_imports(src_root) == []
    assert check_domain_imports_only_stdlib(src_root) == []
    assert check_http_adapters_do_not_import_domain(src_root) == []


@pytest.mark.parametrize(
    "source",
    [
        "from shop.ports import OrderRepositoryPort\n",
        "from shop.application.place_order import PlaceOrder\n",
        "from shop.adapters.outbound import SqlOrderRepository\n",
        "from ..ports import OrderRepositoryPort\n",
        "import shop.application.place_order\n",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from ..ports import P\n",
    ],
)
def test_checker_flags_domain_importing_outward(tmp_path: Path, source: str) -> None:
    src_root = _tree_with(tmp_path, **{"shop/domain/order.py": source})
    violations = check_domain_is_inward_only(src_root)
    assert len(violations) == 1, violations
    assert violations[0].startswith("shop/domain/order.py:")


@pytest.mark.parametrize(
    "source",
    [
        "from warehouse.domain import Stock\n",
        "from warehouse.application.reserve import Reserve\n",
        "from warehouse.ports import StockPort\n",
        "from warehouse.adapters.outbound import SqlStock\n",
        "import warehouse.domain\n",
    ],
)
def test_checker_flags_cross_context_import(tmp_path: Path, source: str) -> None:
    """Strict reading: another context's ports/ and adapters/ are off-limits too."""
    src_root = _tree_with(tmp_path, **{"shop/application/place_order.py": source})
    violations = check_no_cross_context_imports(src_root)
    assert len(violations) == 1, violations
    assert violations[0].startswith("shop/application/place_order.py:")
    assert "warehouse" in violations[0]


def test_the_composition_root_may_import_every_context(tmp_path: Path) -> None:
    """The exemption works: wiring two contexts together from ``main.py`` is not a violation."""
    src_root = _tree_with(
        tmp_path,
        **{
            "main.py": (
                "from shop.application.place_order import PlaceOrder\nimport warehouse.ports\n"
            )
        },
    )
    assert discover_contexts(src_root) == {"shop", "warehouse"}, "main.py is not a context"
    assert check_no_cross_context_imports(src_root) == []


def test_a_second_flat_module_does_not_get_the_exemption(tmp_path: Path) -> None:
    """The exemption is one name. A module that wants it has to be added on purpose."""
    src_root = _tree_with(
        tmp_path,
        **{"wiring.py": "from shop.application.place_order import PlaceOrder\n"},
    )
    violations = check_no_cross_context_imports(src_root)
    assert len(violations) == 1, violations
    assert violations[0].startswith("wiring.py:")
    assert "'wiring' imports context 'shop'" in violations[0]


HTTP_TREE = {
    "shop/adapters/inbound/__init__.py": "",
    "shop/adapters/inbound/http/__init__.py": "",
    "shop/adapters/inbound/http/router.py": "",
}


@pytest.mark.parametrize(
    "source",
    [
        "from shop.domain.order import Order\n",
        "from shop.domain import money\n",
        "import shop.domain.money\n",
        "from ....domain.order import Order\n",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from shop.domain import order\n",
    ],
)
def test_checker_flags_http_adapter_importing_domain(tmp_path: Path, source: str) -> None:
    src_root = _tree_with(tmp_path, **{**HTTP_TREE, "shop/adapters/inbound/http/router.py": source})
    violations = check_http_adapters_do_not_import_domain(src_root)
    assert len(violations) == 1, violations
    assert violations[0].startswith("shop/adapters/inbound/http/router.py:")


@pytest.mark.parametrize(
    "source",
    [
        "from shop.application.place_order import PlaceOrder\n",
        "from fastapi import APIRouter\nfrom pydantic import BaseModel\n",
        "from ....ports import OrderRepositoryPort\n",
    ],
)
def test_checker_accepts_an_http_adapter_on_its_side(tmp_path: Path, source: str) -> None:
    """Use cases, ports and third-party web libraries are all fair game for a route."""
    src_root = _tree_with(tmp_path, **{**HTTP_TREE, "shop/adapters/inbound/http/router.py": source})
    assert check_http_adapters_do_not_import_domain(src_root) == []


@pytest.mark.parametrize(
    "source",
    [
        "from shop.domain.errors import ShopError\n",
        "from ....domain.errors import ShopError\n",
        "import shop.domain.errors\n",
    ],
)
def test_an_http_adapter_may_name_the_errors_it_maps(tmp_path: Path, source: str) -> None:
    """The one carve-out: a status table cannot be written without the exception classes."""
    src_root = _tree_with(tmp_path, **{**HTTP_TREE, "shop/adapters/inbound/http/errors.py": source})
    assert check_http_adapters_do_not_import_domain(src_root) == []


def test_the_carve_out_is_one_module_and_not_a_prefix(tmp_path: Path) -> None:
    """``domain.errors`` is allowed; ``domain.errors_and_values`` is a different module."""
    assert frozenset({"errors"}) == HTTP_MAY_IMPORT_FROM_DOMAIN
    src_root = _tree_with(
        tmp_path,
        **{**HTTP_TREE, "shop/adapters/inbound/http/errors.py": "from shop.domain import values\n"},
    )
    assert len(check_http_adapters_do_not_import_domain(src_root)) == 1


def test_the_http_rule_does_not_fire_on_other_adapters(tmp_path: Path) -> None:
    """An outbound repository maps rows onto entities; naming them is its whole job."""
    src_root = _tree_with(
        tmp_path,
        **{"shop/adapters/outbound/repo.py": "from shop.domain.order import Order\n"},
    )
    assert check_http_adapters_do_not_import_domain(src_root) == []


@pytest.mark.parametrize(
    "source",
    ["import httpx\n", "from sqlalchemy.orm import Session\n", "import pydantic.v1\n"],
)
def test_checker_flags_third_party_import_in_domain(tmp_path: Path, source: str) -> None:
    src_root = _tree_with(tmp_path, **{"shop/domain/order.py": source})
    violations = check_domain_imports_only_stdlib(src_root)
    assert len(violations) == 1, violations
    assert violations[0].startswith("shop/domain/order.py:")


def test_checker_reports_accurate_line_numbers(tmp_path: Path) -> None:
    """A checker that pointed at the wrong line would still 'catch' violations."""
    src_root = _tree_with(
        tmp_path,
        **{"shop/domain/order.py": "from decimal import Decimal\n\n\nimport httpx\n"},
    )
    assert check_domain_imports_only_stdlib(src_root)[0].startswith("shop/domain/order.py:4:")


def test_relative_import_resolution_ascends_correctly(tmp_path: Path) -> None:
    """``from ...x import y`` must resolve against the package, not the module."""
    src_root = _tree_with(
        tmp_path,
        **{"shop/adapters/outbound/repo.py": "from ...domain.order import Order\n"},
    )
    module = next(m for m in iter_modules(src_root) if m.path.name == "repo.py")
    assert module.parts == ("shop", "adapters", "outbound", "repo")
    assert imports_of(module)[0].parts == ("shop", "domain", "order")
    assert check_no_cross_context_imports(src_root) == []
