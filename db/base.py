# db/base.py
"""SQLAlchemy async engine, session factory, and Base for SecureGuard Drift."""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///data/snapshots.db",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    **({"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}),
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
