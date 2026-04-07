"""Connections API routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from pnpg.api.auth import get_current_user
from pnpg.api.deps import get_db_pool
from pnpg.api.middleware import limiter
from pnpg.config import DEFAULT_CONFIG
from pnpg.db.queries import COUNT_CONNECTIONS, SELECT_CONNECTIONS


router = APIRouter(tags=["connections"])


@router.get("/connections")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def get_connections(
    request: Request,
    process: str | None = None,
    dst_ip: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _current_user: str = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
) -> dict:
    """Return paginated connection rows."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    offset = (page - 1) * page_size
    async with db_pool.acquire() as conn:
        total = await conn.fetchval(COUNT_CONNECTIONS, process, dst_ip, from_ts, to_ts)
        rows = await conn.fetch(
            SELECT_CONNECTIONS,
            process,
            dst_ip,
            from_ts,
            to_ts,
            page_size,
            offset,
        )

    return {
        "data": [dict(row) for row in rows],
        "pagination": {"page": page, "page_size": page_size, "total": total},
    }
