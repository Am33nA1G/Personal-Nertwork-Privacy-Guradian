"""Tests for purge scheduler helpers."""

import time
import unittest.mock as mock

import pytest

from pnpg.db.queries import PURGE_ALERTS, PURGE_CONNECTIONS


def _make_pool_and_conn():
    conn = mock.AsyncMock()
    acquire_cm = mock.AsyncMock()
    acquire_cm.__aenter__.return_value = conn
    acquire_cm.__aexit__.return_value = False

    pool = mock.MagicMock()
    pool.acquire.return_value = acquire_cm
    return pool, conn


@pytest.mark.asyncio
async def test_purge_old_data_executes_delete():
    from pnpg.scheduler import purge_old_data

    pool, conn = _make_pool_and_conn()
    conn.execute.side_effect = ["DELETE 1", "DELETE 0", "DELETE 1", "DELETE 0"]

    await purge_old_data(
        pool,
        {"retention_connections_days": 30, "retention_alerts_days": 90},
    )

    calls = conn.execute.await_args_list
    assert calls[0].args == (PURGE_CONNECTIONS, 30)
    assert calls[2].args == (PURGE_ALERTS, 90)


@pytest.mark.asyncio
async def test_purge_old_data_pool_none_noop():
    from pnpg.scheduler import purge_old_data

    await purge_old_data(None, {"retention_connections_days": 30})


def test_log_metrics_logs_info():
    from pnpg import scheduler

    with mock.patch.object(scheduler, "logger") as mock_logger:
        scheduler.log_metrics([3], [1], [time.monotonic() - 5.0])

    assert mock_logger.info.called
    assert "OBS-04 metrics" in mock_logger.info.call_args.args[0]


@pytest.mark.asyncio
async def test_setup_scheduler_creates_scheduler():
    """setup_scheduler returns a running AsyncIOScheduler with two jobs."""
    from pnpg.scheduler import setup_scheduler

    pool = mock.AsyncMock()

    scheduler = setup_scheduler(pool, {"purge_schedule_hour": 3}, drop_counter=[0])

    try:
        jobs = scheduler.get_jobs()
        job_ids = {job.id for job in jobs}
        assert "nightly-purge" in job_ids
        assert "obs-04-metrics" in job_ids
    finally:
        scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_setup_scheduler_pool_none_noop():
    """setup_scheduler works fine when db_pool is None."""
    from pnpg.scheduler import setup_scheduler

    scheduler = setup_scheduler(None, {}, drop_counter=[0])

    try:
        assert scheduler is not None
    finally:
        scheduler.shutdown(wait=False)
