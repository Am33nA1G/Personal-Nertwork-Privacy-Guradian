"""Tests for pnpg.db.pool — create_pool success and graceful failure."""

import unittest.mock as mock

import pytest


@pytest.mark.asyncio
async def test_create_pool_success():
    """create_pool returns the pool object on success."""
    from pnpg.db.pool import create_pool

    mock_pool = mock.MagicMock()

    async def fake_create_pool(*args, **kwargs):
        return mock_pool

    with mock.patch("asyncpg.create_pool", side_effect=fake_create_pool):
        result = await create_pool("postgresql://user:pass@localhost:5432/pnpg")

    assert result is mock_pool


@pytest.mark.asyncio
async def test_create_pool_os_error_returns_none(caplog):
    """create_pool returns None (not raises) when PostgreSQL is unreachable."""
    from pnpg.db.pool import create_pool

    async def fake_create_pool(*args, **kwargs):
        raise OSError("Connection refused")

    with mock.patch("asyncpg.create_pool", side_effect=fake_create_pool):
        with caplog.at_level("WARNING"):
            result = await create_pool("postgresql://user:pass@localhost:5432/pnpg")

    assert result is None
    assert "DB pool creation failed" in caplog.text


@pytest.mark.asyncio
async def test_create_pool_postgres_error_returns_none(caplog):
    """create_pool returns None (not raises) on asyncpg.PostgresError."""
    import asyncpg
    from pnpg.db.pool import create_pool

    async def fake_create_pool(*args, **kwargs):
        raise asyncpg.PostgresError("Auth failed")

    with mock.patch("asyncpg.create_pool", side_effect=fake_create_pool):
        with caplog.at_level("WARNING"):
            result = await create_pool("postgresql://user:pass@localhost:5432/pnpg")

    assert result is None
    assert "DB pool creation failed" in caplog.text


@pytest.mark.asyncio
async def test_create_pool_custom_size_params():
    """create_pool passes min_size and max_size to asyncpg.create_pool."""
    from pnpg.db.pool import create_pool

    captured_kwargs = {}

    async def fake_create_pool(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return mock.MagicMock()

    with mock.patch("asyncpg.create_pool", side_effect=fake_create_pool):
        await create_pool("postgresql://localhost/pnpg", min_size=3, max_size=20)

    assert captured_kwargs["min_size"] == 3
    assert captured_kwargs["max_size"] == 20

