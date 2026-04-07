"""System status and health routes."""

import time

from fastapi import APIRouter, Depends, Request

from pnpg.api.auth import get_current_user
from pnpg.api.deps import get_db_pool


router = APIRouter(tags=["system"])


@router.get("/status")
async def get_status(
    request: Request,
    _current_user: str = Depends(get_current_user),
) -> dict:
    """Return capture status for the authenticated UI."""
    interface = request.app.state.config.get("interface") or "auto"
    started_at = getattr(request.app.state, "started_at", time.monotonic())
    return {
        "data": {
            "capture": "running",
            "interface": interface,
            "uptime": max(0.0, time.monotonic() - started_at),
            "probe_type": request.app.state.probe_type,
        }
    }


@router.get("/health")
async def get_health(request: Request, db_pool=Depends(get_db_pool)) -> dict:
    """Return public health details without auth."""
    db_status = "unavailable"
    if db_pool is not None:
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("SELECT 1")
            db_status = "ok"
        except Exception:  # noqa: BLE001
            db_status = "unavailable"

    return {
        "data": {
            "status": "ok",
            "probe": request.app.state.probe_type,
            "db": db_status,
            "stream": "ok",
        }
    }
