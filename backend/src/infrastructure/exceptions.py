"""
Shared infrastructure-level exceptions.

These live outside any single bounded context (Admission, Enrollment, etc.)
because they represent failures of the infrastructure itself, not violations
of business rules. Any repository adapter, across any domain, can raise these.

Domain-specific exceptions (ApplicationNotFoundException, etc.) still live in
their own domain's exceptions module and extend the base categories from
domain_exceptions.py — this module only adds the ExternalServiceException
subtypes relevant to database access.
"""

from domain.exceptions import ExternalServiceException, ConflictException


# ============================================================
# Connectivity & capacity
# ============================================================

class DatabaseUnavailableException(ExternalServiceException):
    """Raised when the database cannot be reached at all — connection
    refused, DNS failure, or all retry attempts exhausted."""
    code = "DATABASE_UNAVAILABLE"

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Database is unavailable: {reason}")


class ConnectionPoolExhaustedException(ExternalServiceException):
    """Raised when the app's own connection pool has no connections left
    to hand out. Distinct from DatabaseUnavailableException — the DB server
    itself may be perfectly healthy; the app is the bottleneck."""
    code = "DATABASE_CONNECTION_POOL_EXHAUSTED"

    def __init__(self, pool_size: int, timeout_seconds: float):
        self.pool_size = pool_size
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Could not acquire a database connection from the pool "
            f"(size={pool_size}) within {timeout_seconds}s."
        )


# ============================================================
# Query execution failures
# ============================================================

class QueryTimeoutException(ExternalServiceException):
    """Raised when a specific query exceeded its allowed execution time.
    The DB is up — this operation specifically was too slow."""
    code = "DATABASE_QUERY_TIMEOUT"

    def __init__(self, operation: str, timeout_seconds: float):
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Query for operation '{operation}' exceeded {timeout_seconds}s timeout."
        )


class TransactionDeadlockException(ExternalServiceException):
    """Raised when the database detects a deadlock or serialization
    failure between concurrent transactions. Almost always transient —
    the calling adapter method should retry before this ever reaches
    the service layer (see retry wiring below)."""
    code = "DATABASE_TRANSACTION_DEADLOCK"

    def __init__(self, operation: str):
        self.operation = operation
        super().__init__(f"Transaction deadlock detected during '{operation}'.")


# ============================================================
# Constraint-related (translated from driver errors)
# ============================================================

class UnexpectedConstraintViolationException(ExternalServiceException):
    """Fallback for a constraint violation the adapter didn't recognize
    well enough to translate into a specific domain exception (e.g. an
    unfamiliar check-constraint name). This should be rare — its presence
    in logs is a signal to add a proper translation case, not a normal
    user-facing outcome."""
    code = "DATABASE_UNEXPECTED_CONSTRAINT_VIOLATION"

    def __init__(self, constraint_name: str, raw_error: str):
        self.constraint_name = constraint_name
        self.raw_error = raw_error
        super().__init__(
            f"Unrecognized constraint violation on '{constraint_name}': {raw_error}"
        )


class StaleWriteException(ConflictException):
    """Optimistic concurrency failure — the row was modified by someone
    else between when this operation read it and when it tried to write.
    Unlike the exceptions above, this IS business-meaningful (a real
    conflict a user needs to know about and possibly re-do their action
    against fresh data), so it extends ConflictException, not
    ExternalServiceException."""
    code = "DATABASE_STALE_WRITE"

    def __init__(self, entity_type: str, entity_id: str, expected_version: int, actual_version: int):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"{entity_type} {entity_id} was modified by another process "
            f"(expected version {expected_version}, found {actual_version})."
        )