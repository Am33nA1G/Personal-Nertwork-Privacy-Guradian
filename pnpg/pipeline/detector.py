"""Detector helpers and state."""

import ipaddress
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class DetectorState:
    connection_timestamps: dict = field(default_factory=dict)
    first_seen: dict = field(default_factory=dict)
    rate_limiter: dict = field(default_factory=dict)
    tor_exit_nodes: frozenset = field(default_factory=frozenset)
    allowlist: list = field(default_factory=list)
    suppressed_alert_ids: set = field(default_factory=set)
    suppressed_rules: set = field(default_factory=set)


def load_tor_exit_nodes(path: str) -> frozenset:
    entries: set[str] = set()

    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                entries.add(str(ipaddress.ip_address(line)))
    except FileNotFoundError:
        logger.warning("TOR exit node list not found at %s", path)
        return frozenset()

    return frozenset(entries)


def _process_key(event: dict) -> str:
    process_name = event["process_name"]
    if process_name != "unknown process":
        return process_name
    return f"unknown_process_{event.get('pid', -1)}"


def _update_connection_rate(process_key: str, state: DetectorState, config: dict) -> int:
    _ = config
    timestamps = state.connection_timestamps.setdefault(process_key, [])
    now = time.monotonic()
    timestamps.append(now)
    cutoff = now - 60
    state.connection_timestamps[process_key] = [
        timestamp for timestamp in timestamps if timestamp >= cutoff
    ]
    return len(state.connection_timestamps[process_key])


def _make_alert(
    event,
    rule_id,
    severity,
    reason,
    confidence,
    recommended_action,
    suppressed=False,
) -> dict:
    return {
        "alert_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": severity,
        "rule_id": rule_id,
        "reason": reason,
        "confidence": confidence,
        "process_name": event.get("process_name", "unknown process"),
        "pid": event.get("pid", -1),
        "dst_ip": event.get("dst_ip", ""),
        "dst_hostname": event.get("dst_hostname", ""),
        "recommended_action": recommended_action,
        "suppressed": suppressed,
    }


def _is_allowlisted(event: dict, state: DetectorState) -> bool:
    now = datetime.now(timezone.utc)

    for rule in state.allowlist:
        expires_at = rule.get("expires_at")
        if expires_at is not None and now > expires_at:
            continue

        rule_process_name = rule.get("process_name")
        if (
            rule_process_name is not None
            and rule_process_name != event.get("process_name")
        ):
            continue

        if (
            rule.get("dst_ip") == event.get("dst_ip")
            or rule.get("dst_hostname") == event.get("dst_hostname")
        ):
            return True

    return False


def _is_rate_limited(
    rule_id: str, process_key: str, state: DetectorState, config: dict
) -> bool:
    key = (rule_id, process_key)
    limit = config.get("alert_rate_limit_per_sec", 1)
    now = time.monotonic()
    last = state.rate_limiter.get(key, 0.0)

    if now - last < (1.0 / limit):
        return True

    state.rate_limiter[key] = now
    return False


def rule_det01_unknown_domain(event, config, state) -> dict | None:
    _ = config, state
    dst_ip = event.get("dst_ip", "")
    dst_hostname = event.get("dst_hostname", "")

    if not dst_ip:
        return None
    if dst_hostname and dst_hostname != dst_ip:
        return None

    address = ipaddress.ip_address(dst_ip)
    if address.is_private or address.is_loopback:
        return None

    return _make_alert(
        event,
        rule_id="DET-01",
        severity="WARNING",
        reason=f"No reverse DNS record for {dst_ip}",
        confidence=0.5,
        recommended_action="MONITOR",
    )


def rule_det02_rate_spike(event, config, state) -> dict | None:
    process_key = _process_key(event)
    count = _update_connection_rate(process_key, state, config)
    threshold = config.get("connection_rate_threshold_per_min", 100)

    if count > threshold:
        return _make_alert(
            event,
            rule_id="DET-02",
            severity="HIGH",
            reason=(
                f"{event.get('process_name', 'unknown')} exceeded "
                f"{threshold} connections/min (current: {count})"
            ),
            confidence=0.85,
            recommended_action="REVIEW",
        )

    return None


def rule_det03_unusual_port(event, config, state) -> dict | None:
    dst_port = event.get("dst_port", 0)
    port_allowlist = config.get(
        "port_allowlist", [80, 443, 53, 123, 5353, 8080, 8443]
    )
    if dst_port in port_allowlist:
        return None

    process_name = event.get("process_name", "")
    known_processes = config.get("known_processes", [])
    is_unknown = process_name == "unknown process"
    process_key = _process_key(event)
    count = len(state.connection_timestamps.get(process_key, []))
    rate_threshold = config.get("connection_rate_threshold_per_min", 100)
    is_rate_spike = count > rate_threshold
    _ = known_processes

    if not is_unknown and not is_rate_spike:
        return None

    return _make_alert(
        event,
        rule_id="DET-03",
        severity="WARNING",
        reason=(
            f"Unusual port {dst_port} from "
            f"{'unknown process' if is_unknown else process_name + ' (rate spike)'}"
        ),
        confidence=0.6,
        recommended_action="INVESTIGATE",
    )


def rule_det04_unknown_process(event, config, state) -> dict | None:
    _ = config, state
    if event.get("process_name") == "unknown process":
        return _make_alert(
            event,
            rule_id="DET-04",
            severity="ALERT",
            reason=(
                f"Connection from unresolvable process "
                f"(PID {event.get('pid', -1)}) to {event.get('dst_ip', '')}"
            ),
            confidence=0.7,
            recommended_action="INVESTIGATE",
        )

    return None


def rule_det05_blocklisted(event, config, state) -> dict | None:
    _ = config, state
    threat_intel = event.get("threat_intel", {})
    if threat_intel.get("is_blocklisted") is True:
        return _make_alert(
            event,
            rule_id="DET-05",
            severity="CRITICAL",
            reason=(
                "Connection to blocklisted destination "
                f"{event.get('dst_ip', '')}/{event.get('dst_hostname', '')}"
            ),
            confidence=0.95,
            recommended_action="BLOCK",
        )

    return None


def rule_det06_tor_exit_node(event, config, state) -> dict | None:
    _ = config
    dst_ip = event.get("dst_ip", "")
    if dst_ip and dst_ip in state.tor_exit_nodes:
        return _make_alert(
            event,
            rule_id="DET-06",
            severity="HIGH",
            reason=f"Connection to TOR exit node {dst_ip}",
            confidence=0.9,
            recommended_action="REVIEW",
        )

    return None


def rule_det07_new_destination(event, config, state) -> dict | None:
    _ = config
    process_key = _process_key(event)
    dst_ip = event.get("dst_ip", "")
    if not dst_ip:
        return None

    seen = state.first_seen.setdefault(process_key, set())
    if dst_ip in seen:
        return None

    seen.add(dst_ip)
    return _make_alert(
        event,
        rule_id="DET-07",
        severity="LOW",
        reason=(
            f"First connection from {event.get('process_name', 'unknown')} to {dst_ip}"
        ),
        confidence=0.3,
        recommended_action="MONITOR",
    )


async def detect_event(event: dict, config: dict, state: DetectorState) -> list[dict]:
    alerts = []
    rules = [
        rule_det01_unknown_domain,
        rule_det02_rate_spike,
        rule_det03_unusual_port,
        rule_det04_unknown_process,
        rule_det05_blocklisted,
        rule_det06_tor_exit_node,
        rule_det07_new_destination,
    ]

    for rule in rules:
        try:
            alert = rule(event, config, state)
            if alert is None:
                continue
            if _is_allowlisted(event, state):
                continue
            if alert.get("alert_id") in state.suppressed_alert_ids:
                continue
            if (alert.get("rule_id"), event.get("process_name")) in state.suppressed_rules:
                continue

            process_key = _process_key(event)
            if _is_rate_limited(alert["rule_id"], process_key, state, config):
                continue

            alerts.append(alert)
        except Exception as e:
            logger.error(
                "Rule %s failed for event %s: %s",
                rule.__name__,
                event.get("dst_ip", ""),
                e,
                exc_info=True,
            )
            continue

    return alerts
