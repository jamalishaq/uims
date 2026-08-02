"""Architecture fitness test: the dependency rule.

Statically checks the import graph of ``src/`` without importing anything under test.
Three rules, per CLAUDE.md sections 3 and 4:

(a) A module under ``<context>/domain/`` imports nothing from ``application/``, ``ports/``
    or ``adapters/`` — of its own context or any other. Dependencies point inward only.
(b) A module in one context imports nothing from another context, at all. Cross-context
    access goes through query ports typed in the *consuming* context's own language, with
    anti-corruption translation in the consumer's own adapter.
(c) A module under ``<context>/domain/`` imports no third-party package — stdlib only.

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

DOMAIN = "domain"
OUTWARD_LAYERS = frozenset({"application", "ports", "adapters"})


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


# ---- the three rules ----


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
    """(b) No module may import another context, at any layer."""
    contexts = discover_contexts(src_root)
    violations = []
    for module in iter_modules(src_root):
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
