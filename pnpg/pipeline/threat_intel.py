"""Threat intelligence blocklist - local IP/domain blocklist checker.

THREAT-01: Check dst_ip and dst_domain against local blocklist.
THREAT-02: Blocklist stored locally - no external network calls.
THREAT-03: Frozenset lookup - microsecond latency.
THREAT-04: Log THREATINTEL_STALE if blocklist older than 24 hours.
THREAT-05: Flag blocklisted destinations with is_blocklisted: true + source name.
"""

import logging
import os
import time

logger = logging.getLogger(__name__)

SECONDS_IN_DAY = 86400

_blocklist: frozenset[str] = frozenset()


def load_blocklist(path: str = "data/blocklist.txt") -> None:
    global _blocklist

    try:
        entries: set[str] = set()
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                entry = line.split("\t", 1)[0].strip()
                if entry:
                    entries.add(entry)
    except FileNotFoundError:
        _blocklist = frozenset()
        logger.warning(
            "Blocklist file not found at %s - threat intel disabled", path
        )
        return

    _blocklist = frozenset(entries)
    logger.info("Loaded %s blocklist entries from %s", len(_blocklist), path)


def check_threat_intel(event: dict) -> dict:
    dst_ip = event.get("dst_ip") or ""
    dst_hostname = event.get("dst_hostname") or ""
    is_blocklisted = dst_ip in _blocklist or dst_hostname in _blocklist

    return {
        **event,
        "threat_intel": {
            "is_blocklisted": is_blocklisted,
            "source": "ipsum" if is_blocklisted else None,
        },
    }


def check_blocklist_freshness(
    path: str, max_age_seconds: float = 24 * 3600
) -> None:
    try:
        age = time.time() - os.path.getmtime(path)
    except FileNotFoundError:
        logger.warning("THREATINTEL_STALE: blocklist file not found at %s", path)
        return

    if age > max_age_seconds:
        logger.warning(
            "THREATINTEL_STALE: blocklist at %s is %.1f days old (limit: %.1f days)",
            path,
            age / SECONDS_IN_DAY,
            max_age_seconds / SECONDS_IN_DAY,
        )
