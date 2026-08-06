"""The ``Credential`` aggregate."""

import pytest

from identity.domain.credential import Credential
from identity.domain.errors import (
    CredentialInactiveError,
    InvalidLoginIdError,
    InvalidScopeError,
    MissingIdentifierError,
)
from identity.domain.values import PasswordHash, Role, Scope, ScopeKind

PASSWORD = "correct-horse-battery"


def a_credential(**overrides) -> Credential:
    return Credential.issue(
        **{
            "credential_id": "CRED-1",
            "login_id": "DEPT-CSC",
            "principal_id": "DEPT-CSC",
            "role": Role.DEPARTMENT,
            "scope_unit_id": "DEPT-CSC",
            "password": PASSWORD,
            **overrides,
        }
    )


# ---- issuing ----


def test_an_issued_credential_is_active_and_authenticates() -> None:
    credential = a_credential()
    assert credential.is_active
    assert credential.authenticate(PASSWORD)


def test_an_issued_credential_refuses_the_wrong_password() -> None:
    assert not a_credential().authenticate("not-the-password")


def test_issuing_derives_the_scope_kind_from_the_role() -> None:
    """The mismatched combination is unconstructible rather than merely refused."""
    assert a_credential(role=Role.LECTURER, scope_unit_id="LEC-7").scope == Scope(
        ScopeKind.LECTURER, "LEC-7"
    )


def test_a_student_logs_in_with_their_matric_number() -> None:
    """Confirmed in auth.md: the number they are given is the one they type."""
    student = a_credential(
        login_id="260591001", principal_id="STU-1", role=Role.STUDENT, scope_unit_id="STU-1"
    )
    assert student.login_id == "260591001"
    assert student.covers(ScopeKind.STUDENT, "STU-1")


def test_the_password_is_not_reachable_from_the_credential() -> None:
    credential = a_credential()
    assert PASSWORD not in repr(credential)
    assert credential.password_hash.encoded not in repr(credential)


# ---- construction guards ----


@pytest.mark.parametrize("field", ["credential_id", "principal_id"])
def test_a_blank_identifier_is_refused(field: str) -> None:
    with pytest.raises(MissingIdentifierError):
        a_credential(**{field: "  "})


def test_a_login_id_with_whitespace_in_it_is_refused() -> None:
    with pytest.raises(InvalidLoginIdError):
        a_credential(login_id="DEPT CSC")


def test_a_role_scope_mismatch_is_refused() -> None:
    """The check ``restore`` exists to keep: a row nobody can authorize stays a row."""
    with pytest.raises(InvalidScopeError) as refused:
        Credential(
            credential_id="CRED-1",
            login_id="FAC-SCI",
            principal_id="FAC-SCI",
            role=Role.FACULTY,
            scope=Scope(ScopeKind.STUDENT, "STU-1"),
            password_hash=PasswordHash.of(PASSWORD),
        )
    assert "faculty" in str(refused.value)


def test_a_role_must_be_a_role() -> None:
    with pytest.raises(InvalidScopeError):
        a_credential(role="department")


# ---- authenticating ----


def test_authenticating_a_deactivated_credential_raises() -> None:
    """A different fact from a wrong password, and the domain keeps them different."""
    credential = a_credential()
    credential.deactivate()
    with pytest.raises(CredentialInactiveError):
        credential.authenticate(PASSWORD)


def test_deactivation_is_idempotent() -> None:
    credential = a_credential()
    credential.deactivate()
    credential.deactivate()
    assert not credential.is_active


def test_reactivating_restores_the_password_that_was_always_there() -> None:
    credential = a_credential()
    credential.deactivate()
    credential.reactivate()
    assert credential.authenticate(PASSWORD)


# ---- changing a password ----


def test_changing_the_password_retires_the_old_one() -> None:
    credential = a_credential()
    credential.change_password("a-brand-new-password")
    assert credential.authenticate("a-brand-new-password")
    assert not credential.authenticate(PASSWORD)


def test_a_deactivated_credential_cannot_change_its_password() -> None:
    credential = a_credential()
    credential.deactivate()
    with pytest.raises(CredentialInactiveError):
        credential.change_password("a-brand-new-password")


def test_rehashing_leaves_the_password_working() -> None:
    credential = a_credential()
    credential.rehash(PASSWORD)
    assert credential.authenticate(PASSWORD)


def test_rehashing_a_current_hash_changes_nothing() -> None:
    """Only a hash that is actually stale is worth the scrypt cost."""
    credential = a_credential()
    before = credential.password_hash.encoded
    credential.rehash(PASSWORD)
    assert credential.password_hash.encoded == before


def test_rehashing_a_stale_hash_upgrades_it() -> None:
    credential = a_credential()
    algorithm, _, r, p, salt, key = credential.password_hash.encoded.split("$")
    credential.password_hash = PasswordHash("$".join((algorithm, "1024", r, p, salt, key)))
    credential.rehash(PASSWORD)
    assert not credential.password_hash.needs_rehash
    assert credential.authenticate(PASSWORD)


# ---- reconstitution ----


def test_restore_rebuilds_a_deactivated_credential() -> None:
    original = a_credential()
    original.deactivate()
    restored = Credential.restore(
        credential_id=original.credential_id,
        login_id=original.login_id,
        principal_id=original.principal_id,
        role=original.role,
        scope=original.scope,
        password_hash=original.password_hash,
        is_active=original.is_active,
    )
    assert restored == original
    assert not restored.is_active


def test_restore_validates_the_combination_it_is_handed() -> None:
    """A repository writing through private attributes would skip exactly this."""
    with pytest.raises(InvalidScopeError):
        Credential.restore(
            credential_id="CRED-1",
            login_id="LEC-7",
            principal_id="LEC-7",
            role=Role.LECTURER,
            scope=Scope(ScopeKind.UNIVERSITY, "UNI-LASU"),
            password_hash=PasswordHash.of(PASSWORD),
            is_active=True,
        )


# ---- scope ----


def test_a_university_credential_covers_every_unit() -> None:
    university = a_credential(
        login_id="UNI-LASU",
        principal_id="UNI-LASU",
        role=Role.UNIVERSITY,
        scope_unit_id="UNI-LASU",
    )
    assert university.covers(ScopeKind.DEPARTMENT, "DEPT-MTH")
    assert university.covers(ScopeKind.STUDENT, "STU-9")


def test_a_department_credential_covers_only_its_own_department() -> None:
    credential = a_credential()
    assert credential.covers(ScopeKind.DEPARTMENT, "DEPT-CSC")
    assert not credential.covers(ScopeKind.DEPARTMENT, "DEPT-MTH")
