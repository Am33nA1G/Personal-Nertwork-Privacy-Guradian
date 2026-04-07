"""Background scheduler for retention purge and OBS-04 metrics."""

import logging
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from pnpg.db.queries import PURGE_ALERTS, PURGE_CONNECTIONS


logger = logging.getLogger(__name__)


async def purge_old_data(db_pool, config: dict) -> None:
    """Delete retained rows in chunks until no expired rows remain."""
    if db_pool is None:
        return

    conn_days = config.get("retention_connections_days", 30)
    alert_days = config.get("retention_alerts_days", 90)

    async with db_pool.acquire() as conn:
        deleted = 1
        while deleted > 0:
            result = await conn.execute(PURGE_CONNECTIONS, conn_days)
            deleted = int(result.split()[-1]) if result else 0

        deleted = 1
        while deleted > 0:
            result = await conn.execute(PURGE_ALERTS, alert_days)
            deleted = int(result.split()[-1]) if result else 0

    logger.info(
        "Purge complete: connections > %d days, alerts > %d days",
        conn_days,
        alert_days,
    )


def log_metrics(drop_counter: list[int], last_count: list[int], last_time: list[float]) -> None:
    """Emit OBS-04 counters on a fixed interval."""
    now = time.monotonic()
    elapsed = now - last_time[0]
    current = drop_counter[0]
    drops_since = current - last_count[0]
    last_count[0] = current
    last_time[0] = now

    logger.info(
        "OBS-04 metrics - drops_since_last: %d, total_drops: %d, interval: %.1fs",
        drops_since,
        current,
        elapsed,
    )


def setup_scheduler(db_pool, config: dict, drop_counter: list[int]) -> AsyncIOScheduler:
    """Create and start the Phase 5 background scheduler."""
    scheduler = AsyncIOScheduler()
    purge_hour = config.get("purge_schedule_hour", 2)
    scheduler.add_job(
        purge_old_data,
        "cron",
        hour=purge_hour,
        minute=0,
        args=[db_pool, config],
        id="nightly-purge",
    )

    last_count = [0]
    last_time = [time.monotonic()]
    scheduler.add_job(
        log_metrics,
        "interval",
        seconds=5,
        args=[drop_counter, last_count, last_time],
        id="obs-04-metrics",
    )
    scheduler.start()
    return scheduler
