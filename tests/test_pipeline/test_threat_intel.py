"""RED-phase tests for threat intelligence blocklist enrichment."""

import logging
import os
import random
import time

from pnpg.pipeline.threat_intel import (
    check_blocklist_freshness,
    check_threat_intel,
    load_blocklist,
)


def test_blocklisted_ip(tmp_path):
    """THREAT-01/05: A blocklisted IP is flagged with source ipsum."""
    blocklist = tmp_path / "blocklist.txt"
    blocklist.write_text("1.2.3.4\t5\n", encoding="utf-8")

    load_blocklist(str(blocklist))
    result = check_threat_intel({"dst_ip": "1.2.3.4", "dst_hostname": ""})

    assert result["threat_intel"] == {"is_blocklisted": True, "source": "ipsum"}


def test_blocklisted_domain(tmp_path):
    """THREAT-01: A blocklisted domain is flagged."""
    blocklist = tmp_path / "blocklist.txt"
    blocklist.write_text("evil.com\t3\n", encoding="utf-8")

    load_blocklist(str(blocklist))
    result = check_threat_intel({"dst_ip": "5.6.7.8", "dst_hostname": "evil.com"})

    assert result["threat_intel"] == {"is_blocklisted": True, "source": "ipsum"}


def test_clean_ip(tmp_path):
    """THREAT-05: A clean destination is marked as not blocklisted."""
    blocklist = tmp_path / "blocklist.txt"
    blocklist.write_text("1.2.3.4\t5\n", encoding="utf-8")

    load_blocklist(str(blocklist))
    result = check_threat_intel({"dst_ip": "9.9.9.9", "dst_hostname": "clean.com"})

    assert result["threat_intel"] == {"is_blocklisted": False, "source": None}


def test_missing_file(caplog):
    """THREAT-02: Missing blocklist logs a warning and disables threat intel."""
    with caplog.at_level(logging.WARNING):
        load_blocklist("/nonexistent/blocklist.txt")

    assert "not found" in caplog.text.lower()

    result = check_threat_intel({"dst_ip": "1.2.3.4"})
    assert result["threat_intel"]["is_blocklisted"] is False


def test_lookup_latency(tmp_path):
    """THREAT-03: Blocklist lookups should remain fast at scale."""
    blocklist = tmp_path / "blocklist.txt"
    entries = [f"10.0.{i // 256}.{i % 256}\t1" for i in range(10000)]
    blocklist.write_text("\n".join(entries) + "\n", encoding="utf-8")

    load_blocklist(str(blocklist))

    rng = random.Random(0)
    start = time.perf_counter()
    for _ in range(10000):
        ip = f"10.0.{rng.randrange(0, 40)}.{rng.randrange(0, 256)}"
        check_threat_intel({"dst_ip": ip, "dst_hostname": ""})
    elapsed = time.perf_counter() - start

    assert elapsed < 0.05


def test_stale_warning(caplog, tmp_path):
    """THREAT-04: Stale blocklist files emit THREATINTEL_STALE."""
    blocklist = tmp_path / "blocklist.txt"
    blocklist.write_text("1.2.3.4\t5\n", encoding="utf-8")
    stale_time = time.time() - (25 * 3600)
    os.utime(blocklist, (stale_time, stale_time))

    with caplog.at_level(logging.WARNING):
        check_blocklist_freshness(str(blocklist))

    assert "THREATINTEL_STALE" in caplog.text


def test_flag_fields(tmp_path):
    """THREAT-05: The threat_intel payload has the expected keys and values."""
    blocklist = tmp_path / "blocklist.txt"
    blocklist.write_text("10.0.0.1\t2\n", encoding="utf-8")

    load_blocklist(str(blocklist))
    result = check_threat_intel({"dst_ip": "10.0.0.1", "dst_hostname": ""})

    assert "threat_intel" in result
    assert set(result["threat_intel"]) == {"is_blocklisted", "source"}
    assert result["threat_intel"]["is_blocklisted"] is True
    assert result["threat_intel"]["source"] == "ipsum"


def test_immutable(tmp_path):
    """Threat intel enrichment must not mutate the original event dict."""
    blocklist = tmp_path / "blocklist.txt"
    blocklist.write_text("1.2.3.4\t5\n", encoding="utf-8")

    load_blocklist(str(blocklist))
    event = {"dst_ip": "1.2.3.4", "dst_hostname": ""}

    result = check_threat_intel(event)

    assert "threat_intel" not in event
    assert "threat_intel" in result


def test_comment_lines_skipped(tmp_path):
    """Comment lines are ignored while real entries still load."""
    blocklist = tmp_path / "blocklist.txt"
    blocklist.write_text("# comment\n1.2.3.4\t5\n", encoding="utf-8")

    load_blocklist(str(blocklist))

    blocked = check_threat_intel({"dst_ip": "1.2.3.4"})
    comment = check_threat_intel({"dst_ip": "# comment"})

    assert blocked["threat_intel"]["is_blocklisted"] is True
    assert comment["threat_intel"]["is_blocklisted"] is False
