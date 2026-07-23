import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from infrastructure.database.connection import DatabaseFactory
from transport.http.dependencies import dependency_registry
from transport.http.routers import (
    application_router,
    account_router
)
from .exception_handlers import handle_domain_exception, handle_unexpected_exception

from domain.exceptions import DomainException

# 1. Setup Production Logging Properties
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)


# 2. Managing the Infrastructure Lifecycle (Lifespan Context)
@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """
    Handles application setup and graceful shutdown routines.
    Ensures that physical database socket pools are safely closed.
    """
    # ---- STARTUP PHASE ----
    # Pull credentials securely from environment configurations
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/university_db")
    
    logger.info("Initializing connection pool factories via asyncpg...")
    db_factory = DatabaseFactory(
        database_url=database_url,
        pool_size=20,
        max_overflow=10
    )
    
    # Register our running factory instance into the dependency container
    dependency_registry.set_db_factory(db_factory)
    logger.info("Application infrastructure successfully wired up.")
    
    yield  # The application runs while suspended right here
    
    # ---- SHUTDOWN PHASE (Graceful Shutdown Handling) ----
    logger.info("SIGTERM/SIGINT captured. Initiating graceful application shutdown...")
    await db_factory.close_engine()
    logger.info("Cleanup completed. HTTP server terminated safely.")


# 3. Initialize the FastAPI Framework Engine
app = FastAPI(
    title="University Core Management Engine",
    description="A high-concurrency, decoupled REST API built using Clean/Hexagonal Architecture boundaries.",
    version="1.0.0",
    lifespan=app_lifespan
)

# 4. Mount the Transport Layer Routers
app.include_router(application_router)
app.include_router(account_router)

@app.get("/healthz", tags=["System Lifecycle"], summary="Liveness Probe")
async def liveness_probe():
    """Simple transport-layer ping check to verify the app container is awake."""
    return {"status": "healthy"}


# -- Exception Handling --

app.add_exception_handler(DomainException, handle_domain_exception)
app.add_exception_handler(Exception, handle_unexpected_exception)