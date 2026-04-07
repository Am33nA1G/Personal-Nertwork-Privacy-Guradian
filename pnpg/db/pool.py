"""Async PostgreSQL pool helpers."""

import logging

import asyncpg


logger = logging.getLogger(__name__)


async def create_pool(
    dsn: str, min_size: int = 2, max_size: int = 10
) -> asyncpg.Pool | None:
    """Create an asyncpg pool or return None when PostgreSQL is unavailable."""
    try:
        return await asyncpg.create_pool(
            dsn,
            min_size=min_size,
            max_size=max_size,
            command_timeout=5.0,
            server_settings={"application_name": "pnpg"},
        )
    except (OSError, asyncpg.PostgresError) as exc:
        logger.warning("DB pool creation failed (SYS-04): %s", exc)
        return None
