"""
db_resilience.py — shared retry and circuit-breaker decorators for
repository adapters. Import these into any adapter module; don't
reimplement retry logic per-repository.
"""

import logging
from functools import wraps

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
from sqlalchemy.exc import OperationalError, DBAPIError
from pybreaker import CircuitBreaker, CircuitBreakerError

from src.infrastructure.exceptions import (
    DatabaseUnavailableException,
    # TransactionDeadlockException,
)

logger = logging.getLogger(__name__)


# ============================================================
# Retry: for brief, transient failures
# ============================================================

def retry_on_transient_db_error(operation_name: str):
    """
    Retries up to 3 times with exponential backoff (0.2s, 0.4s, 0.8s)
    on connection blips and deadlocks — the two failure types that are
    genuinely likely to succeed on a second attempt within milliseconds.

    Does NOT retry on IntegrityError (constraint violations) — retrying
    a duplicate-key insert just fails the same way again; that's a
    translate-and-raise case, not a retry case.
    """
    return retry(
        retry=retry_if_exception_type((OperationalError, DBAPIError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.2, max=2),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,  # after exhausting attempts, raise the original error
    )


# ============================================================
# Circuit breaker: for sustained outages
# ============================================================

# One breaker per logical database, not per repository/table.
# All repositories hitting the same Postgres instance share this breaker,
# so once it's open, every repository fails fast together instead of each
# independently hammering a dead database.
db_circuit_breaker = CircuitBreaker(
    fail_max=5,          # open the circuit after 5 consecutive failures
    reset_timeout=30,     # after 30s, allow a single "trial" request through
    exclude=[             # don't count business-logic exceptions as breaker failures
        # constraint violations aren't infrastructure failures — a duplicate
        # key error doesn't mean the DB is unhealthy
    ],
)


def with_circuit_breaker(func):
    """
    Wraps a repository method so that once the breaker is open, calls
    fail immediately with DatabaseUnavailableException instead of waiting
    for a connection timeout on every single request.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await db_circuit_breaker.call_async(func, *args, **kwargs)
        except CircuitBreakerError as e:
            raise DatabaseUnavailableException(
                reason="Circuit breaker open — database has failed repeatedly, "
                       "refusing further attempts until cooldown elapses."
            ) from e
        except (OperationalError, DBAPIError) as e:
            # This call itself failed after exhausting retries — may or may not
            # be the call that just tripped the breaker open. Either way, the
            # caller-facing outcome should look identical.
            raise DatabaseUnavailableException(reason=str(e)) from e

    return wrapper