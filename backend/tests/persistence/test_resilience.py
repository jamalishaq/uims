"""The retry policy, tested without a database.

CLAUDE.md section 4 states the resilience pattern as four claims, and each one is a claim
about behaviour under failure — which is exactly the behaviour a passing integration suite
never exercises. A Postgres that is up cannot demonstrate that a deadlock is retried and a
duplicate key is not. So the failures are raised directly here and the policy is watched.

The distinction that earns its own tests is transient versus permanent. Retrying a unique
violation is not merely wasteful: it converts an answer into a delay. The second attempt
fails for the reason the first did, and a caller who could have been told "that id is
taken" instead waits out the backoff first.
"""

import asyncio
import time

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

from persistence import (
    MAX_ATTEMPTS,
    UNIQUE_VIOLATION,
    Failure,
    PersistenceUnavailableError,
    classify,
    normalise_url,
    resilient,
)


class FakePostgresError(Exception):
    """What asyncpg raises, as far as classification is concerned: an exception with a code."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__(f"postgres error {sqlstate}")
        self.sqlstate = sqlstate


def wrapped(sqlstate: str, kind: type[DBAPIError] = OperationalError) -> DBAPIError:
    """The same error as SQLAlchemy hands it over, with the driver's on ``orig``."""
    return kind("SELECT 1", {}, FakePostgresError(sqlstate))


class TestClassification:
    @pytest.mark.parametrize(
        "sqlstate",
        ["40001", "40P01", "53300", "55P03", "57014", "57P01", "57P03", "08006", "08003"],
    )
    def test_the_failures_a_healthy_database_recovers_from_are_transient(
        self, sqlstate: str
    ) -> None:
        assert classify(wrapped(sqlstate)) is Failure.TRANSIENT

    def test_a_unique_violation_is_its_own_kind_and_never_transient(self) -> None:
        """It is how ``add`` learns an id is taken. Retrying would delay that answer."""
        failure = wrapped(UNIQUE_VIOLATION, IntegrityError)

        assert classify(failure) is Failure.DUPLICATE
        assert classify(failure) is not Failure.TRANSIENT

    @pytest.mark.parametrize(
        "sqlstate",
        [
            "23503",  # foreign_key_violation
            "23502",  # not_null_violation
            "23514",  # check_violation
            "22001",  # string_data_right_truncation
            "42703",  # undefined_column — a bug in the adapter, not a blip
            "42P01",  # undefined_table
        ],
    )
    def test_a_statement_the_database_refused_on_its_merits_is_permanent(
        self, sqlstate: str
    ) -> None:
        assert classify(wrapped(sqlstate)) is Failure.PERMANENT

    def test_an_unrecognised_sqlstate_is_permanent(self) -> None:
        """Unclassified is not the same as safe to repeat, and the default has to say so."""
        assert classify(wrapped("XX000")) is Failure.PERMANENT

    def test_a_bare_network_failure_with_no_sqlstate_is_transient(self) -> None:
        assert classify(ConnectionResetError("connection reset by peer")) is Failure.TRANSIENT
        assert classify(TimeoutError()) is Failure.TRANSIENT

    def test_an_ordinary_exception_is_permanent(self) -> None:
        assert classify(ValueError("that is not a session id")) is Failure.PERMANENT


class TestRetrying:
    async def test_a_transient_failure_is_retried_and_can_succeed(self) -> None:
        attempts = 0

        @resilient()
        async def flaky() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise wrapped("40001")
            return "committed"

        assert await flaky() == "committed"
        assert attempts == 3

    async def test_retries_stop_at_three_attempts(self) -> None:
        attempts = 0

        @resilient()
        async def always_failing() -> None:
            nonlocal attempts
            attempts += 1
            raise wrapped("40P01")

        with pytest.raises(PersistenceUnavailableError):
            await always_failing()

        assert attempts == MAX_ATTEMPTS == 3

    async def test_exhausted_retries_surface_as_persistence_unavailable(self) -> None:
        """The port-level type CLAUDE.md section 4 names. No driver exception gets out."""

        @resilient()
        async def always_failing() -> None:
            raise wrapped("08006")

        with pytest.raises(PersistenceUnavailableError) as exhausted:
            await always_failing()

        assert isinstance(exhausted.value.__cause__, OperationalError)
        assert "always_failing" in str(exhausted.value)

    async def test_a_duplicate_is_raised_on_the_first_attempt_without_waiting(self) -> None:
        """The claim that matters: the caller is told, rather than told slowly."""
        attempts = 0
        started = time.perf_counter()

        @resilient()
        async def duplicate_key() -> None:
            nonlocal attempts
            attempts += 1
            raise wrapped(UNIQUE_VIOLATION, IntegrityError)

        with pytest.raises(IntegrityError):
            await duplicate_key()

        assert attempts == 1
        assert time.perf_counter() - started < 0.05

    async def test_a_permanent_failure_is_not_retried(self) -> None:
        attempts = 0

        @resilient()
        async def malformed() -> None:
            nonlocal attempts
            attempts += 1
            raise wrapped("42P01")

        with pytest.raises(OperationalError):
            await malformed()

        assert attempts == 1

    async def test_the_backoff_grows_between_attempts(self) -> None:
        """Exponential with jitter, per section 4. Asserted as ordering, not as durations."""
        moments: list[float] = []

        @resilient()
        async def always_failing() -> None:
            moments.append(time.perf_counter())
            raise wrapped("40001")

        with pytest.raises(PersistenceUnavailableError):
            await always_failing()

        first_gap = moments[1] - moments[0]
        second_gap = moments[2] - moments[1]
        assert first_gap > 0
        assert second_gap > first_gap

    async def test_an_operation_that_never_answers_times_out(self) -> None:
        """The backstop for a connection that has stopped replying rather than failed."""

        @resilient(attempts=1, timeout=0.05)
        async def hanging() -> None:
            await asyncio.sleep(30)

        with pytest.raises(PersistenceUnavailableError):
            await hanging()

    async def test_a_domain_error_passes_straight_through(self) -> None:
        """A repository raises its context's errors too, and they are not failures to retry."""

        class AggregateNotFoundError(Exception):
            pass

        @resilient()
        async def refusing() -> None:
            raise AggregateNotFoundError("nobody stored that")

        with pytest.raises(AggregateNotFoundError):
            await refusing()


class TestUrlNormalisation:
    @pytest.mark.parametrize(
        "given",
        [
            "postgresql://user:pw@localhost:5432/ums",
            "postgres://user:pw@localhost:5432/ums",
            "postgresql+psycopg://user:pw@localhost:5432/ums",
            "postgresql+asyncpg://user:pw@localhost:5432/ums",
        ],
    )
    def test_every_spelling_of_the_dsn_arrives_on_the_async_driver(self, given: str) -> None:
        """One place knows which driver is in use; a deployment may write any of these."""
        assert normalise_url(given) == "postgresql+asyncpg://user:pw@localhost:5432/ums"

    def test_a_url_for_something_else_is_left_alone(self) -> None:
        assert normalise_url("sqlite+aiosqlite:///:memory:") == "sqlite+aiosqlite:///:memory:"
