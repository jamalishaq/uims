import logging
from fastapi import Request
from fastapi.responses import JSONResponse

from .domain.exceptions import (
    DomainException,
    NotFoundException,
    ValidationException,
    ConflictException,
    BusinessRuleViolationException,
    UnauthorizedActionException,
    ExternalServiceException
)

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

def map_exception_to_http_status(err: DomainException) -> int:
    if isinstance(err, NotFoundException):
        return 404
    if isinstance(err, ValidationException):
        return 400
    if isinstance(err, ConflictException):
        return 409
    if isinstance(err, BusinessRuleViolationException):
        return 422
    if isinstance(err, UnauthorizedActionException):
        return 403
    if isinstance(err, ExternalServiceException):
        return 502
    return 500  # fallback for any DomainException not yet categorized

async def handle_domain_exception(request: Request, exc: DomainException) -> JSONResponse:
    status_code = map_exception_to_http_status(exc)

    # Pull structured fields off the exception (application_id, program_id, etc.)
    # without leaking Python internals like `args` or `message` twice.
    details = {
        key: value
        for key, value in vars(exc).items()
        if key != "message"
    }

    if status_code >= 500:
        logger.error("Unhandled domain exception: %s", exc.code, exc_info=exc)
    else:
        logger.info("Domain exception: %s - %s", exc.code, exc.message)

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": details,
            }
        },
    )

async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unexpected error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred."}},
    )