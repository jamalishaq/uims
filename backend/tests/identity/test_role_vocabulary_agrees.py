"""``security`` and ``identity.domain`` say the same words, and this is what keeps them saying it.

``security.py`` restates ``Role``, ``ScopeKind`` and the covering rule rather than importing
them, and the reason is structural rather than a preference: one shared enum would need either
the domain layer importing a flat module — rule (c) of the fitness test permits stdlib only —
or every context importing Identity to guard its routes, which rule (b) forbids outright.

The price of the restatement is that the two can drift, and drift here is not a cosmetic
problem. A role added to Identity and not to ``security`` cannot be guarded against; a covering
rule that widened on one side and not the other would be a 403 in one place and a 200 in
another for the same token. So the agreement is asserted rather than trusted, in the same
arrangement ``tests/academic_records/domain/test_grading_scale.py`` uses for the grading table.

This test module is the only place in the suite that imports both.
"""

import pytest

import security
from identity.domain import values as identity_values


def test_the_two_role_enums_have_identical_members() -> None:
    assert {role.name: role.value for role in identity_values.Role} == {
        role.name: role.value for role in security.Role
    }


def test_the_two_scope_kind_enums_have_identical_members() -> None:
    assert {kind.name: kind.value for kind in identity_values.ScopeKind} == {
        kind.name: kind.value for kind in security.ScopeKind
    }


def test_every_role_maps_to_a_scope_kind_security_also_knows() -> None:
    """A role whose scope kind ``security`` cannot name would tokenise into something unusable."""
    for role in identity_values.Role:
        assert security.ScopeKind(role.scope_kind.value)


@pytest.mark.parametrize("kind", list(identity_values.ScopeKind))
@pytest.mark.parametrize("unit_id", ["DEPT-CSC", "DEPT-MTH"])
def test_the_covering_rule_agrees_on_both_sides(
    kind: identity_values.ScopeKind, unit_id: str
) -> None:
    """The check that matters most: the same token must not be a 403 here and a 200 there."""
    for scope_kind in identity_values.ScopeKind:
        domain_scope = identity_values.Scope(scope_kind, "DEPT-CSC")
        transport_principal = security.Principal(
            subject="P",
            login_id="P",
            role=security.Role(scope_kind.value),
            scope_kind=security.ScopeKind(scope_kind.value),
            scope_id="DEPT-CSC",
        )
        assert domain_scope.covers(kind, unit_id) == transport_principal.covers(
            security.ScopeKind(kind.value), unit_id
        )
