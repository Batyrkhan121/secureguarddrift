# db/migrations/env.py
"""Alembic migration environment — async-capable."""

import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Import models so Base.metadata knows every table
from db.base import Base
from db import models as _models  # noqa: F401 — side-effect import

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/snapshots.db")
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode (emit SQL)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in online mode (async engine)."""
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
