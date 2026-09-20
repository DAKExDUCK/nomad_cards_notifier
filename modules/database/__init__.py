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
        await conn.execute(text(
            "ALTER TABLE fuel_card_operations "
            "ADD COLUMN IF NOT EXISTS occurred_at_datetime TIMESTAMP"
        ))
        await conn.execute(text(
            "UPDATE fuel_card_operations "
            "SET occurred_at_datetime = CASE "
            "WHEN occurred_at ~ '^[0-9]{2}[.][0-9]{2}[.][0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}$' "
            "THEN to_timestamp(occurred_at, 'DD.MM.YYYY HH24:MI:SS')::timestamp "
            "WHEN occurred_at ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$' "
            "THEN to_timestamp(occurred_at, 'YYYY-MM-DD HH24:MI:SS')::timestamp "
            "ELSE NULL END "
            "WHERE occurred_at_datetime IS NULL AND occurred_at IS NOT NULL"
        ))


async def close_db():
    """Close database connection"""
    await engine.dispose()


__all__ = ["async_session", "init_db", "close_db", "DatabaseService"]
