"""Stats API routes."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from pnpg.api.auth import get_current_user
from pnpg.api.deps import get_db_pool
from pnpg.api.middleware import limiter
from pnpg.config import DEFAULT_CONFIG
from pnpg.db.queries import STATS_SUMMARY, STATS_TIMESERIES


router = APIRouter(tags=["stats"])


@router.get("/stats/summary")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def get_stats_summary(
    request: Request,
    _current_user: str = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
) -> dict:
    """Return 24-hour aggregate metrics."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(STATS_SUMMARY)

    payload = dict(row) if row is not None else {}
    payload.setdefault("total_connections", 0)
    payload.setdefault("unique_destinations", 0)
    payload.setdefault("active_alerts", 0)
    payload.setdefault("top_processes", [])
    payload.setdefault("top_destinations", [])
    return {"data": payload}


@router.get("/stats/timeseries")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def get_stats_timeseries(
    request: Request,
    metric: str = "connections",
    interval: str = "1h",
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    _current_user: str = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
) -> dict:
    """Return bucketed metric series."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    _ = metric
    bucket_map = {"1m": "minute", "5m": "minute", "1h": "hour", "1d": "day"}
    bucket = bucket_map.get(interval, "hour")
    end = to_ts or datetime.now(timezone.utc)
    start = from_ts or (end - timedelta(hours=24))

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(STATS_TIMESERIES, bucket, start, end)
    return {"data": [dict(row) for row in rows]}
