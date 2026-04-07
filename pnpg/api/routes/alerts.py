"""Alerts and suppression API routes."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from pnpg.api.auth import get_current_user
from pnpg.api.deps import get_db_pool, get_detector_state
from pnpg.api.middleware import limiter
from pnpg.api.models import AlertAction
from pnpg.config import DEFAULT_CONFIG
from pnpg.db.queries import (
    COUNT_ALERTS,
    INSERT_SUPPRESSION,
    SELECT_ALERTS,
    SELECT_SUPPRESSIONS,
    UPDATE_ALERT_STATUS,
)


router = APIRouter(tags=["alerts"])
DELETE_SUPPRESSION = """
DELETE FROM suppressions
WHERE suppression_id = $1
RETURNING *
"""


@router.get("/alerts")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def get_alerts(
    request: Request,
    status: str | None = None,
    severity: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _current_user: str = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
) -> dict:
    """Return paginated alerts."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    offset = (page - 1) * page_size
    async with db_pool.acquire() as conn:
        total = await conn.fetchval(COUNT_ALERTS, status, severity, from_ts, to_ts)
        rows = await conn.fetch(
            SELECT_ALERTS,
            status,
            severity,
            from_ts,
            to_ts,
            page_size,
            offset,
        )

    return {
        "data": [dict(row) for row in rows],
        "pagination": {"page": page, "page_size": page_size, "total": total},
    }


@router.patch("/alerts/{alert_id}")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def patch_alert(
    alert_id: str,
    body: AlertAction,
    request: Request,
    _current_user: str = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
    detector_state=Depends(get_detector_state),
) -> dict:
    """Suppress or resolve an alert."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    target_status = "suppressed" if body.action == "suppress" else "resolved"
    alert_uuid = UUID(alert_id)

    async with db_pool.acquire() as conn:
        updated = await conn.fetchrow(UPDATE_ALERT_STATUS, alert_uuid, target_status)
        if updated is None:
            raise HTTPException(status_code=404, detail="Alert not found")

        updated_dict = dict(updated)
        if body.action == "suppress":
            await conn.fetchrow(
                INSERT_SUPPRESSION,
                updated_dict.get("rule_id"),
                updated_dict.get("process_name"),
                "single",
                body.reason,
                alert_uuid,
            )
            detector_state.suppressed_alert_ids.add(alert_id)
        else:
            detector_state.suppressed_alert_ids.discard(alert_id)

    return {"data": updated_dict}


@router.get("/suppressions")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def get_suppressions(
    request: Request,
    _current_user: str = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
) -> dict:
    """Return stored suppressions."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(SELECT_SUPPRESSIONS)
    return {"data": [dict(row) for row in rows]}


@router.delete("/suppressions/{suppression_id}")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def delete_suppression(
    suppression_id: str,
    request: Request,
    _current_user: str = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
    detector_state=Depends(get_detector_state),
) -> dict:
    """Delete a stored suppression and update in-memory detector state."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(DELETE_SUPPRESSION, UUID(suppression_id))
        if row is None:
            raise HTTPException(status_code=404, detail="Suppression not found")

    row_dict = dict(row)
    alert_id = row_dict.get("alert_id")
    if alert_id is not None:
        detector_state.suppressed_alert_ids.discard(str(alert_id))
    if row_dict.get("scope") == "rule":
        detector_state.suppressed_rules.discard(
            (row_dict.get("rule_id"), row_dict.get("process_name"))
        )
    return {"data": {"deleted": True}}
