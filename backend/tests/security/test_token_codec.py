"""The token codec: what a token carries, and every way one is refused."""

import time

import jwt
import pytest

import security
from security import (
    ACCESS_TOKEN,
    REFRESH_TOKEN,
    ForbiddenError,
    InvalidTokenError,
    Principal,
    Role,
    ScopeKind,
    TokenCodec,
)

SECRET = "not-a-real-signing-key-but-long-enough-for-hs256"
"""Long enough to satisfy ``MINIMUM_SECRET_BYTES``, and that is the point of the length."""


@pytest.fixture
def codec() -> TokenCodec:
    return TokenCodec(SECRET)


def a_principal(**overrides) -> Principal:
    return Principal(
        **{
            "subject": "DEPT-CSC",
            "login_id": "DEPT-CSC",
            "role": Role.DEPARTMENT,
            "scope_kind": ScopeKind.DEPARTMENT,
            "scope_id": "DEPT-CSC",
            **overrides,
        }
    )


# ---- round trip ----


def test_an_access_token_round_trips(codec: TokenCodec) -> None:
    principal = a_principal()
    assert codec.decode(codec.issue_access(principal)) == principal


def test_a_refresh_token_round_trips(codec: TokenCodec) -> None:
    principal = a_principal()
    token = codec.issue_refresh(principal)
    assert codec.decode(token, expected_type=REFRESH_TOKEN) == principal


def test_a_token_carries_no_name_or_email(codec: TokenCodec) -> None:
    """Section 6's rule about the identity context, applied to the token it issues."""
    claims = jwt.decode(codec.issue_access(a_principal()), SECRET, algorithms=["HS256"])
    assert set(claims) == {
        "sub",
        "login_id",
        "role",
        "scope_kind",
        "scope_id",
        "typ",
        "iss",
        "iat",
        "exp",
    }


def test_the_default_lifetimes_are_the_ones_auth_md_states(codec: TokenCodec) -> None:
    assert codec.access_ttl_seconds == 30 * 60
    assert codec.refresh_ttl_seconds == 12 * 60 * 60


# ---- refusals ----


def test_a_refresh_token_is_not_an_access_token(codec: TokenCodec) -> None:
    """Without the ``typ`` claim the 12-hour lifetime would silently become both lifetimes."""
    with pytest.raises(InvalidTokenError):
        codec.decode(codec.issue_refresh(a_principal()))


def test_an_access_token_is_not_a_refresh_token(codec: TokenCodec) -> None:
    with pytest.raises(InvalidTokenError):
        codec.decode(codec.issue_access(a_principal()), expected_type=REFRESH_TOKEN)


def test_a_token_signed_with_another_key_is_refused(codec: TokenCodec) -> None:
    forged = TokenCodec("a-different-key-also-long-enough-for-hs256").issue_access(a_principal())
    with pytest.raises(InvalidTokenError):
        codec.decode(forged)


def test_an_expired_token_is_refused(codec: TokenCodec) -> None:
    stale = codec.issue_access(a_principal(), now=int(time.time()) - codec.access_ttl_seconds - 1)
    with pytest.raises(InvalidTokenError):
        codec.decode(stale)


def test_a_token_from_another_issuer_is_refused(codec: TokenCodec) -> None:
    other = TokenCodec(SECRET, issuer="somebody-else").issue_access(a_principal())
    with pytest.raises(InvalidTokenError):
        codec.decode(other)


def test_an_unsigned_token_is_refused(codec: TokenCodec) -> None:
    """The ``alg: none`` attack, and the reason ``algorithms=`` is not optional."""
    unsigned = jwt.encode(
        {
            "sub": "UNI-LASU",
            "login_id": "UNI-LASU",
            "role": "university",
            "scope_kind": "university",
            "scope_id": "UNI-LASU",
            "typ": ACCESS_TOKEN,
            "iss": "ums",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
        },
        key="",
        algorithm="none",
    )
    with pytest.raises(InvalidTokenError):
        codec.decode(unsigned)


@pytest.mark.parametrize("missing", ["sub", "login_id", "role", "scope_kind", "scope_id"])
def test_a_token_missing_a_claim_is_refused(codec: TokenCodec, missing: str) -> None:
    claims = jwt.decode(codec.issue_access(a_principal()), SECRET, algorithms=["HS256"])
    del claims[missing]
    with pytest.raises(InvalidTokenError):
        codec.decode(jwt.encode(claims, SECRET, algorithm="HS256"))


def test_a_token_naming_a_role_this_version_does_not_know_is_refused(codec: TokenCodec) -> None:
    claims = jwt.decode(codec.issue_access(a_principal()), SECRET, algorithms=["HS256"])
    claims["role"] = "chancellor"
    with pytest.raises(InvalidTokenError):
        codec.decode(jwt.encode(claims, SECRET, algorithm="HS256"))


def test_every_refusal_says_the_same_thing(codec: TokenCodec) -> None:
    """Which check failed is information about a token the caller is holding."""
    forged = TokenCodec("a-different-key-also-long-enough-for-hs256").issue_access(a_principal())
    stale = codec.issue_access(a_principal(), now=int(time.time()) - 10**6)
    messages = set()
    for token in (forged, stale, codec.issue_refresh(a_principal())):
        with pytest.raises(InvalidTokenError) as refused:
            codec.decode(token)
        messages.add(str(refused.value))
    assert len(messages) == 1


def test_a_codec_refuses_to_exist_without_a_secret() -> None:
    with pytest.raises(ValueError):
        TokenCodec("")


def test_a_codec_refuses_a_secret_too_short_for_hs256() -> None:
    """RFC 7518 section 3.2. A short key signs perfectly, which is why it survives forever."""
    with pytest.raises(ValueError, match="at least 32 bytes"):
        TokenCodec("x" * (security.MINIMUM_SECRET_BYTES - 1))


def test_a_secret_at_the_floor_is_accepted() -> None:
    assert TokenCodec("x" * security.MINIMUM_SECRET_BYTES)


# ---- scope ----


def test_a_principal_covers_its_own_unit() -> None:
    assert a_principal().covers(ScopeKind.DEPARTMENT, "DEPT-CSC")


def test_a_principal_does_not_cover_another_unit() -> None:
    assert not a_principal().covers(ScopeKind.DEPARTMENT, "DEPT-MTH")


@pytest.mark.parametrize("kind", list(ScopeKind))
def test_a_university_principal_covers_everything(kind: ScopeKind) -> None:
    university = a_principal(
        role=Role.UNIVERSITY, scope_kind=ScopeKind.UNIVERSITY, scope_id="UNI-LASU"
    )
    assert university.covers(kind, "anything")


def test_require_scope_raises_on_a_mismatch() -> None:
    with pytest.raises(ForbiddenError) as refused:
        a_principal().require_scope(ScopeKind.DEPARTMENT, "DEPT-MTH")
    assert "DEPT-MTH" in str(refused.value)


def test_require_scope_is_silent_on_a_match() -> None:
    assert a_principal().require_scope(ScopeKind.DEPARTMENT, "DEPT-CSC") is None


def test_require_self_admits_the_principal_and_refuses_anyone_else() -> None:
    student = a_principal(
        subject="STU-1", role=Role.STUDENT, scope_kind=ScopeKind.STUDENT, scope_id="STU-1"
    )
    assert student.require_self("STU-1") is None
    with pytest.raises(ForbiddenError):
        student.require_self("STU-2")


# ---- the role gate ----


class _Request:
    """The two things ``current_principal`` reads off a request, and nothing else."""

    def __init__(self, app, token: str | None) -> None:
        self.app = app
        self.headers = {"authorization": f"Bearer {token}"} if token else {}


class _App:
    def __init__(self, codec: TokenCodec) -> None:
        self.state = type("State", (), {security.STATE_KEY: codec})()


def request_for(codec: TokenCodec, principal: Principal | None) -> _Request:
    return _Request(_App(codec), codec.issue_access(principal) if principal else None)


def test_requires_admits_a_permitted_role(codec: TokenCodec) -> None:
    guard = security.requires(Role.DEPARTMENT, Role.UNIVERSITY)
    assert guard(request_for(codec, a_principal())) == a_principal()


def test_requires_refuses_a_role_it_does_not_name(codec: TokenCodec) -> None:
    guard = security.requires(Role.UNIVERSITY)
    with pytest.raises(ForbiddenError) as refused:
        guard(request_for(codec, a_principal()))
    assert "university" in str(refused.value)


def test_a_guarded_route_needs_a_token_at_all(codec: TokenCodec) -> None:
    with pytest.raises(security.AuthenticationRequiredError):
        security.requires(Role.UNIVERSITY)(request_for(codec, None))


def test_the_scheme_is_matched_case_insensitively(codec: TokenCodec) -> None:
    request = request_for(codec, a_principal())
    request.headers["authorization"] = request.headers["authorization"].replace("Bearer", "bearer")
    assert security.current_principal(request) == a_principal()


def test_a_non_bearer_authorization_header_is_a_401(codec: TokenCodec) -> None:
    request = request_for(codec, a_principal())
    request.headers["authorization"] = "Basic dXNlcjpwYXNz"
    with pytest.raises(security.AuthenticationRequiredError):
        security.current_principal(request)


def test_requires_needs_at_least_one_role() -> None:
    """A guard that admitted everybody would look exactly like a guard."""
    with pytest.raises(ValueError):
        security.requires()


def test_the_lecturer_guard_has_no_university_fallback(codec: TokenCodec) -> None:
    """Deliberate: the domain check behind grade submission has no meaning for a non-lecturer.

    A university-scoped caller admitted here would reach ``lecturer.is_assigned_to(course)``
    and fail it forever, which is a worse answer than the 403 it gets instead.
    """
    guard = security.Lecturer.__metadata__[0].dependency
    university = a_principal(
        role=Role.UNIVERSITY, scope_kind=ScopeKind.UNIVERSITY, scope_id="UNI-LASU"
    )
    with pytest.raises(ForbiddenError):
        guard(request_for(codec, university))


def test_an_unwired_app_refuses_to_serve_a_guarded_route(codec: TokenCodec) -> None:
    """Failing loudly beats serving a guarded route with no way to check a token."""
    unwired = _Request(type("App", (), {"state": type("State", (), {})()})(), "irrelevant")
    with pytest.raises(RuntimeError, match="composition root"):
        security.current_principal(unwired)
