"""Persist pipeline events to PostgreSQL and NDJSON logs."""

import json
import logging
import uuid
from datetime import datetime, timezone

from pnpg.db.queries import INSERT_ALERT, INSERT_CONNECTION, UPSERT_PROCESS


logger = logging.getLogger(__name__)


def _coerce_datetime(value):
    """Return a datetime instance for asyncpg TIMESTAMPTZ parameters."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _coerce_uuid(value):
    """Return a UUID instance for asyncpg UUID parameters."""
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        return uuid.UUID(value)
    return value


def _coerce_text(value):
    """Return a text value for asyncpg TEXT parameters."""
    if value is None:
        return None
    return str(value)


async def storage_writer(
    event: dict, alerts: list[dict], db_pool, ndjson_writer: "NdjsonWriter"
) -> None:
    """Write the connection event and any alerts to storage backends."""
    if db_pool is not None:
        try:
            event_id = _coerce_uuid(event.get("event_id") or str(uuid.uuid4()))
            event_timestamp = _coerce_datetime(event.get("timestamp"))
            severity = event.get("severity", "INFO")
            threat_intel = event.get("threat_intel", {})

            async with db_pool.acquire() as conn:
                await conn.execute(
                    INSERT_CONNECTION,
                    event_id,
                    event_timestamp,
                    _coerce_text(event.get("process_name", "unknown process")),
                    _coerce_text(event.get("process_path")),
                    event.get("pid"),
                    _coerce_text(event.get("src_ip")),
                    event.get("src_port"),
                    _coerce_text(event.get("dst_ip")),
                    event.get("dst_port"),
                    _coerce_text(event.get("dst_hostname")),
                    _coerce_text(event.get("dst_country")),
                    _coerce_text(event.get("dst_asn")),
                    _coerce_text(event.get("dst_org")),
                    _coerce_text(event.get("protocol")),
                    event.get("bytes_sent", 0),
                    event.get("bytes_recv", 0),
                    _coerce_text(event.get("state")),
                    threat_intel.get("is_blocklisted", False),
                    _coerce_text(threat_intel.get("source")),
                    _coerce_text(severity),
                    json.dumps(event, default=str),
                )

                for alert in alerts:
                    alert_id = _coerce_uuid(alert.get("alert_id"))
                    alert_timestamp = _coerce_datetime(alert.get("timestamp"))
                    await conn.execute(
                        INSERT_ALERT,
                        alert_id,
                        alert_timestamp,
                        _coerce_text(alert.get("severity")),
                        _coerce_text(alert.get("rule_id")),
                        _coerce_text(alert.get("reason")),
                        alert.get("confidence"),
                        _coerce_text(alert.get("process_name")),
                        alert.get("pid"),
                        _coerce_text(alert.get("dst_ip")),
                        _coerce_text(alert.get("dst_hostname")),
                        _coerce_text(alert.get("recommended_action")),
                        alert.get("suppressed", False),
                        _coerce_text(alert.get("status", "active")),
                    )

                await conn.execute(
                    UPSERT_PROCESS,
                    _coerce_text(event.get("process_name", "unknown process")),
                    _coerce_text(event.get("process_path")),
                    datetime.now(timezone.utc),
                )
        except Exception as exc:  # noqa: BLE001
            logger.error("storage_writer DB error: %s", exc)
    else:
        logger.warning("DB unavailable - skipping DB insert (SYS-04)")

    await ndjson_writer.append("connections", event)
    for alert in alerts:
        await ndjson_writer.append("alerts", alert)
