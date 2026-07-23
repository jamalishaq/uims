import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

class DatabaseFactory:
    def __init__(self, database_url: str, pool_size: int = 20, max_overflow: int = 10):
        """
        Initializes the SQLAlchemy AsyncEngine with asyncpg.
        
        :param database_url: Connection string (must start with postgresql+asyncpg://)
        :param pool_size: The number of persistent connections to keep open in the pool.
        :param max_overflow: The max number of connections to create beyond pool_size during traffic spikes.
        """
        self._engine: AsyncEngine = create_async_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,      
            pool_recycle=1800,       
            pool_timeout=30,        
            echo=False               
        )
        
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Crucial for Clean Architecture so detached models keep their attributes
            autocommit=False,
            autoflush=False
        )

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        A context manager that provides an isolated transactional scope.
        Automatically handles commits, rollbacks, and connection closing.
        """
        session: AsyncSession = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Database transaction failed; rolled back changes. Error: %s", str(e))
            raise e
        finally:
            await session.close()

    async def close_engine(self) -> None:
        """
        Disposes of the entire connection pool. 
        To be called explicitly during the Transport Layer's Graceful Shutdown process.
        """
        logger.info("Disposing of the database connection pool...")
        await self._engine.dispose()
        logger.info("Database connection pool closed successfully.")


    

# When I wan to shard database
    # class ShardedDatabaseManager:
    #     def __init__(self):
    #         # 1. This dictionary is our REGISTRY
    #         self._shard_registry = {} 

    #     def initialize_shards(self, shard_configs: list):
    #         for config in shard_configs:
    #             # 2. We use a FACTORY logic to create the heavy connection pool
    #             pool = create_async_engine(config["url"], pool_size=10)
                
    #             # 3. We store it in our REGISTRY under its shard identifier
    #             self._shard_registry[config["shard_id"]] = pool

    #     def get_connection_for_shard(self, shard_id: int):
    #         # 4. Looking up the live connection from the registry instantly
    #         return self._shard_registry.get(shard_id)