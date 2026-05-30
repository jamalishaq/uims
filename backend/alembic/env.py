import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.core.config import settings
from app.core.database import Base

# Register all models so Alembic sees them
import app.models.user          # noqa: F401
import app.models.academic      # noqa: F401
import app.models.student       # noqa: F401
import app.models.staff         # noqa: F401
import app.models.calendar      # noqa: F401
import app.models.course        # noqa: F401
import app.models.grade         # noqa: F401
import app.models.attendance    # noqa: F401
import app.models.assignment    # noqa: F401
import app.models.payment       # noqa: F401
import app.models.admission     # noqa: F401
import app.models.hostel        # noqa: F401
import app.models.library       # noqa: F401
import app.models.thesis        # noqa: F401
import app.models.notification  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
