"""Threat detection and remediation API routes."""

import logging
import subprocess
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from pnpg.api.auth import get_current_user
from pnpg.api.deps import get_db_pool
from pnpg.api.middleware import limiter
from pnpg.config import DEFAULT_CONFIG
from pnpg.db.queries import (
    COUNT_THREATS,
    GET_THREAT_BY_PID,
    INSERT_THREAT,
    SELECT_THREATS,
    UPDATE_THREAT_STATUS,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["threats"])


class RemediationError(Exception):
    """Raised when remediation action fails."""

    pass


def kill_process_windows(pid: int) -> bool:
    """Kill a process on Windows using taskkill.

    Args:
        pid: Process ID to terminate

    Returns:
        True if successful, False otherwise

    Raises:
        RemediationError: If the kill command fails
    """
    try:
        logger.info(f"Attempting to kill process PID={pid}")
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            error_msg = result.stderr or "Unknown error"
            raise RemediationError(f"taskkill failed: {error_msg}")

        logger.info(f"Successfully killed process PID={pid}")
        return True
    except subprocess.TimeoutExpired:
        raise RemediationError(f"taskkill timeout for PID={pid}")
    except Exception as e:
        raise RemediationError(f"Failed to kill process: {str(e)}")


def block_ip_windows_firewall(ip: str) -> bool:
    """Block an IP address using Windows Firewall.

    Args:
        ip: IP address to block

    Returns:
        True if successful

    Raises:
        RemediationError: If the block command fails
    """
    try:
        logger.info(f"Attempting to block IP={ip} via Windows Firewall")
        rule_name = f"PNPG_Block_{ip.replace('.', '_')}"

        # Create inbound block rule
        result = subprocess.run(
            [
                "netsh",
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name={rule_name}",
                f"dir=out",
                f"action=block",
                f"remoteip={ip}",
                "protocol=any",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            error_msg = result.stderr or "Unknown error"
            raise RemediationError(f"netsh firewall failed: {error_msg}")

        logger.info(f"Successfully blocked IP={ip}")
        return True
    except subprocess.TimeoutExpired:
        raise RemediationError(f"netsh firewall timeout for IP={ip}")
    except Exception as e:
        raise RemediationError(f"Failed to block IP: {str(e)}")


@router.get("/threats")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def get_threats(
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
    """Return paginated threats."""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    offset = (page - 1) * page_size
    async with db_pool.acquire() as conn:
        total = await conn.fetchval(COUNT_THREATS, status, severity, from_ts, to_ts)
        rows = await conn.fetch(
            SELECT_THREATS,
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


@router.post("/threats/{pid}/kill")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def kill_threat_process(
    pid: int,
    request: Request,
    _current_user: str = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
) -> dict:
    """Kill a malicious process by PID and mark threat as remediated.

    Args:
        pid: Process ID to terminate

    Returns:
        Remediation status
    """
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Validate PID is reasonable
    if pid <= 0:
        raise HTTPException(status_code=400, detail="Invalid PID")

    # Get threat record
    async with db_pool.acquire() as conn:
        threat = await conn.fetchrow(GET_THREAT_BY_PID, pid)
        if threat is None:
            raise HTTPException(status_code=404, detail="Threat not found")

        threat_id = threat["threat_id"]

        try:
            # Attempt to kill process
            kill_process_windows(pid)

            # Update threat status to killed
            await conn.execute(
                UPDATE_THREAT_STATUS,
                threat_id,
                "remediated",
                "killed",
            )

            return {
                "success": True,
                "message": f"Process {pid} terminated successfully",
                "threat_id": str(threat_id),
                "remediation_status": "killed",
            }
        except RemediationError as e:
            logger.error(f"Remediation failed for PID={pid}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/threats/{pid}/block-ip")
@limiter.limit(DEFAULT_CONFIG["api_rate_limit"])
async def block_threat_ip(
    pid: int,
    request: Request,
    _current_user: str = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
) -> dict:
    """Block an IP address associated with a threat via Windows Firewall.

    Args:
        pid: Process ID (used to look up threat)

    Returns:
        Blocking status
    """
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    if pid <= 0:
        raise HTTPException(status_code=400, detail="Invalid PID")

    async with db_pool.acquire() as conn:
        threat = await conn.fetchrow(GET_THREAT_BY_PID, pid)
        if threat is None:
            raise HTTPException(status_code=404, detail="Threat not found")

        threat_id = threat["threat_id"]
        dst_ip = threat["dst_ip"]

        try:
            # Block the IP
            block_ip_windows_firewall(dst_ip)

            # Update threat status
            await conn.execute(
                UPDATE_THREAT_STATUS,
                threat_id,
                "remediated",
                "blocked",
            )

            return {
                "success": True,
                "message": f"IP {dst_ip} blocked successfully",
                "threat_id": str(threat_id),
                "ip": dst_ip,
                "remediation_status": "blocked",
            }
        except RemediationError as e:
            logger.error(f"IP block failed for {dst_ip}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
