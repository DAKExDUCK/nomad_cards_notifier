from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DB_URL

# Async engine
engine = create_async_engine(
    DB_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# Async session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Import service after initialization
from modules.database.models import Base
from modules.database.service import DatabaseService  # pylint: disable=wrong-import-position


async def init_db():
    """Initialize database (create tables)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "ALTER TABLE fuel_card_operations "
            "ADD COLUMN IF NOT EXISTS fuel_balance VARCHAR(100)"
        ))


async def close_db():
    """Close database connection"""
    await engine.dispose()


__all__ = ["async_session", "init_db", "close_db", "DatabaseService"]
