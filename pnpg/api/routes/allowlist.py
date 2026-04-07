"""Allowlist CRUD API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from pnpg.api.auth import get_current_user
from pnpg.api.deps import get_db_pool, get_detector_state
from pnpg.api.middleware import limiter
from pnpg.api.models import AllowlistRuleCreate
from pnpg.config import DEFAULT_CONFIG
from pnpg.db.queries import DELETE_ALLOWLIST, INSERT_ALLOWLIST, SELECT_ALLOWLIST


router = APIRouter(tags=["allowlist"])


@router.get("/allowlist")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def get_allowlist(
    request: Request,
    _current_user: str = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
) -> dict:
    """Return all allowlist rules."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(SELECT_ALLOWLIST)
    return {"data": [dict(row) for row in rows]}


@router.post("/allowlist")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def create_allowlist_rule(
    body: AllowlistRuleCreate,
    request: Request,
    _current_user: str = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
    detector_state=Depends(get_detector_state),
) -> dict:
    """Create an allowlist rule and sync it to in-memory detector state."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            INSERT_ALLOWLIST,
            body.process_name,
            body.dst_ip,
            body.dst_hostname,
            body.expires_at,
            body.reason,
        )

    row_dict = dict(row)
    detector_state.allowlist.append(
        {
            "rule_id": str(row_dict["rule_id"]),
            "process_name": body.process_name,
            "dst_ip": body.dst_ip,
            "dst_hostname": body.dst_hostname,
            "expires_at": body.expires_at,
        }
    )
    return {"data": row_dict}


@router.delete("/allowlist/{rule_id}")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def delete_allowlist_rule(
    rule_id: str,
    request: Request,
    _current_user: str = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
    detector_state=Depends(get_detector_state),
) -> dict:
    """Delete an allowlist rule and sync detector state."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(DELETE_ALLOWLIST, UUID(rule_id))
        if row is None:
            raise HTTPException(status_code=404, detail="Rule not found")

    detector_state.allowlist = [
        rule
        for rule in detector_state.allowlist
        if rule.get("rule_id") != rule_id
    ]
    return {"data": {"deleted": True}}
