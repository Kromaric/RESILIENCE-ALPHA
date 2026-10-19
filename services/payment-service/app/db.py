from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.config import Settings


def utcnow() -> datetime:
    """Date UTC sans fuseau, cohérente avec les colonnes DATETIME de MariaDB."""
    return datetime.now(UTC).replace(tzinfo=None)


def iso_utc(value: datetime) -> str:
    return value.replace(tzinfo=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.sqlalchemy_url(),
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=0,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=1800,
    )


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session
