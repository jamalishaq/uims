"""Roles, scopes and password hashes."""

import pytest

from identity.domain.errors import (
    InvalidLoginIdError,
    InvalidPasswordError,
    InvalidPasswordHashError,
    InvalidScopeError,
    MissingIdentifierError,
)
from identity.domain.values import (
    MINIMUM_PASSWORD_LENGTH,
    PasswordHash,
    Role,
    Scope,
    ScopeKind,
    require_login_id,
    require_password,
)

PASSWORD = "correct-horse-battery"


# ---- roles and their scope kinds ----


def test_every_role_has_a_scope_kind() -> None:
    """The table is exhaustive, so a role added without one fails here and not in a request."""
    assert {role: role.scope_kind for role in Role} == {
        Role.UNIVERSITY: ScopeKind.UNIVERSITY,
        Role.FACULTY: ScopeKind.FACULTY,
        Role.DEPARTMENT: ScopeKind.DEPARTMENT,
        Role.LECTURER: ScopeKind.LECTURER,
        Role.STUDENT: ScopeKind.STUDENT,
    }


def test_the_five_roles_are_the_actors_section_6_confirmed() -> None:
    """Written out independently, as the source of truth it is checked against."""
    assert {role.value for role in Role} == {
        "university",
        "faculty",
        "department",
        "lecturer",
        "student",
    }


# ---- scope ----


def test_a_scope_covers_its_own_unit() -> None:
    scope = Scope(ScopeKind.DEPARTMENT, "DEPT-CSC")
    assert scope.covers(ScopeKind.DEPARTMENT, "DEPT-CSC")


def test_a_scope_does_not_cover_another_unit_of_its_own_kind() -> None:
    scope = Scope(ScopeKind.DEPARTMENT, "DEPT-CSC")
    assert not scope.covers(ScopeKind.DEPARTMENT, "DEPT-MTH")


def test_a_scope_does_not_cover_a_different_kind() -> None:
    scope = Scope(ScopeKind.DEPARTMENT, "DEPT-CSC")
    assert not scope.covers(ScopeKind.FACULTY, "DEPT-CSC")


@pytest.mark.parametrize("kind", list(ScopeKind))
def test_a_university_scope_covers_everything(kind: ScopeKind) -> None:
    """The one widening rule in the system, and the whole meaning of university-scoped."""
    assert Scope(ScopeKind.UNIVERSITY, "UNI-LASU").covers(kind, "anything-at-all")


def test_a_faculty_scope_does_not_reach_into_its_departments() -> None:
    """Identity does not hold the structure, so it may not answer structural questions.

    Widening here would make this context the second place the faculty→department tree lives,
    which is the failure it was carved out to avoid.
    """
    assert not Scope(ScopeKind.FACULTY, "FAC-SCI").covers(ScopeKind.DEPARTMENT, "DEPT-CSC")


def test_a_scope_needs_a_unit_id() -> None:
    with pytest.raises(MissingIdentifierError):
        Scope(ScopeKind.DEPARTMENT, "   ")


def test_a_scope_kind_must_be_a_scope_kind() -> None:
    with pytest.raises(InvalidScopeError):
        Scope("department", "DEPT-CSC")  # type: ignore[arg-type]


# ---- password hashing ----


def test_a_hash_verifies_the_password_it_was_made_from() -> None:
    assert PasswordHash.of(PASSWORD).verify(PASSWORD)


def test_a_hash_refuses_a_different_password() -> None:
    assert not PasswordHash.of(PASSWORD).verify(PASSWORD + "!")


def test_a_hash_refuses_a_password_that_is_a_prefix_of_the_right_one() -> None:
    assert not PasswordHash.of(PASSWORD).verify(PASSWORD[:-1])


def test_two_hashes_of_one_password_differ() -> None:
    """Per-credential salt: identical passwords must not produce identical rows."""
    assert PasswordHash.of(PASSWORD).encoded != PasswordHash.of(PASSWORD).encoded


def test_verify_answers_false_for_a_non_string() -> None:
    """A yes/no question answers yes or no; raising on some wrong answers would be an oracle."""
    assert not PasswordHash.of(PASSWORD).verify(None)  # type: ignore[arg-type]


def test_verify_answers_false_for_a_password_too_short_to_have_been_hashed() -> None:
    assert not PasswordHash.of(PASSWORD).verify("x")


def test_the_encoding_carries_its_cost_parameters() -> None:
    algorithm, n, r, p, salt, key = PasswordHash.of(PASSWORD).encoded.split("$")
    assert algorithm == "scrypt"
    assert (int(n), int(r), int(p)) == (16384, 8, 1)
    assert salt and key


def test_a_hash_made_with_current_parameters_does_not_need_rehashing() -> None:
    assert not PasswordHash.of(PASSWORD).needs_rehash


def test_a_hash_made_with_weaker_parameters_needs_rehashing() -> None:
    """What storing the parameters in the string buys: the floor can be raised later."""
    weak = PasswordHash.of(PASSWORD)
    algorithm, _, r, p, salt, key = weak.encoded.split("$")
    assert PasswordHash("$".join((algorithm, "1024", r, p, salt, key))).needs_rehash


@pytest.mark.parametrize(
    "encoded",
    [
        "",
        "scrypt$16384$8$1$only-five-fields",
        "bcrypt$16384$8$1$c2FsdA==$a2V5",
        "scrypt$0$8$1$c2FsdA==$a2V5",
        "scrypt$notanumber$8$1$c2FsdA==$a2V5",
        "scrypt$16384$8$1$not base64!$a2V5",
    ],
)
def test_a_stored_hash_this_context_did_not_write_is_refused(encoded: str) -> None:
    """Refused at the door, rather than becoming a credential whose failure looks like a typo."""
    with pytest.raises(InvalidPasswordHashError):
        PasswordHash(encoded)


def test_a_hash_never_prints_itself() -> None:
    """A hash in a traceback is an offline attack somebody else runs at their leisure."""
    hashed = PasswordHash.of(PASSWORD)
    assert hashed.encoded not in repr(hashed)
    assert hashed.encoded not in str(hashed)
    assert "redacted" in repr(hashed)


def test_a_password_shorter_than_the_floor_is_refused() -> None:
    with pytest.raises(InvalidPasswordError):
        PasswordHash.of("x" * (MINIMUM_PASSWORD_LENGTH - 1))


def test_a_password_at_the_floor_is_accepted() -> None:
    assert PasswordHash.of("x" * MINIMUM_PASSWORD_LENGTH)


def test_a_password_keeps_its_surrounding_whitespace() -> None:
    """Stripping would silently admit a different password from the one that was typed."""
    padded = f"  {PASSWORD}  "
    assert require_password(padded) == padded
    assert PasswordHash.of(padded).verify(padded)
    assert not PasswordHash.of(padded).verify(PASSWORD)


# ---- login ids ----


def test_a_login_id_is_stripped() -> None:
    assert require_login_id("  DEPT-CSC  ") == "DEPT-CSC"


def test_a_login_id_may_not_contain_whitespace() -> None:
    with pytest.raises(InvalidLoginIdError):
        require_login_id("DEPT CSC")


def test_a_blank_login_id_is_refused() -> None:
    with pytest.raises(MissingIdentifierError):
        require_login_id("   ")
