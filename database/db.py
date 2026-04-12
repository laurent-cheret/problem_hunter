import logging
from datetime import date
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from config import DATABASE_URL
from database.models import Base, DailyQuota

logger = logging.getLogger(__name__)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialised.")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_or_create_quota(session: AsyncSession) -> DailyQuota:
    """Return today's quota row, creating it if necessary."""
    today = date.today()
    result = await session.execute(
        select(DailyQuota).where(DailyQuota.quota_date == today)
    )
    quota = result.scalar_one_or_none()
    if quota is None:
        quota = DailyQuota(quota_date=today, reports_generated=0)
        session.add(quota)
        await session.flush()
    return quota
