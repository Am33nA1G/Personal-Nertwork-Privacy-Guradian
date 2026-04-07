"""Tests for graceful shutdown cleanup in main.py."""

import asyncio
import threading
import unittest.mock as mock

import pytest


@pytest.mark.asyncio
async def test_ndjson_flush_called_on_shutdown():
    from pnpg import main

    stop_event = threading.Event()
    supervisor_task = asyncio.create_task(asyncio.sleep(3600))
    poller_task = asyncio.create_task(asyncio.sleep(3600))
    worker_task = asyncio.create_task(asyncio.sleep(3600))
    ws_manager = mock.AsyncMock()
    scheduler = mock.Mock()
    ndjson_writer = mock.AsyncMock()
    db_pool = mock.AsyncMock()

    with mock.patch.object(main, "close_readers"):
        await main.shutdown_runtime(
            stop_event,
            supervisor_task,
            poller_task,
            worker_task,
            ws_manager,
            scheduler,
            ndjson_writer,
            db_pool,
        )

    ndjson_writer.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_db_pool_closed_on_shutdown():
    from pnpg import main

    stop_event = threading.Event()
    supervisor_task = asyncio.create_task(asyncio.sleep(3600))
    poller_task = asyncio.create_task(asyncio.sleep(3600))
    worker_task = asyncio.create_task(asyncio.sleep(3600))
    ws_manager = mock.AsyncMock()
    scheduler = mock.Mock()
    ndjson_writer = mock.AsyncMock()
    db_pool = mock.AsyncMock()

    with mock.patch.object(main, "close_readers"):
        await main.shutdown_runtime(
            stop_event,
            supervisor_task,
            poller_task,
            worker_task,
            ws_manager,
            scheduler,
            ndjson_writer,
            db_pool,
        )

    db_pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_ws_manager_stopped_on_shutdown():
    from pnpg import main

    stop_event = threading.Event()
    supervisor_task = asyncio.create_task(asyncio.sleep(3600))
    poller_task = asyncio.create_task(asyncio.sleep(3600))
    worker_task = asyncio.create_task(asyncio.sleep(3600))
    ws_manager = mock.AsyncMock()
    scheduler = mock.Mock()
    ndjson_writer = mock.AsyncMock()
    db_pool = mock.AsyncMock()

    with mock.patch.object(main, "close_readers"):
        await main.shutdown_runtime(
            stop_event,
            supervisor_task,
            poller_task,
            worker_task,
            ws_manager,
            scheduler,
            ndjson_writer,
            db_pool,
        )

    ws_manager.stop.assert_awaited_once()
