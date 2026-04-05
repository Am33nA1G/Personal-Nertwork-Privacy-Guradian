"""Tests for detector helpers and state."""

import itertools
from datetime import datetime, timedelta, timezone
import uuid

import pytest

from pnpg.config import DEFAULT_CONFIG
from pnpg.pipeline.detector import (
    DetectorState,
    _is_allowlisted,
    _is_rate_limited,
    _make_alert,
    _process_key,
    _update_connection_rate,
    detect_event,
    load_tor_exit_nodes,
    rule_det01_unknown_domain,
    rule_det02_rate_spike,
    rule_det03_unusual_port,
    rule_det04_unknown_process,
    rule_det05_blocklisted,
    rule_det06_tor_exit_node,
    rule_det07_new_destination,
)


def test_detector_state_defaults():
    state = DetectorState()

    assert state.connection_timestamps == {}
    assert state.first_seen == {}
    assert state.rate_limiter == {}
    assert state.tor_exit_nodes == frozenset()
    assert state.allowlist == []
    assert state.suppressed_alert_ids == set()
    assert state.suppressed_rules == set()


def test_make_alert_has_expected_keys(enriched_event):
    alert = _make_alert(
        enriched_event,
        rule_id="DET-01",
        severity="high",
        reason="test reason",
        confidence=0.95,
        recommended_action="test action",
    )

    assert set(alert) == {
        "alert_id",
        "timestamp",
        "severity",
        "rule_id",
        "reason",
        "confidence",
        "process_name",
        "pid",
        "dst_ip",
        "dst_hostname",
        "recommended_action",
        "suppressed",
    }
    assert len(alert) == 12


def test_make_alert_generates_uuid4(enriched_event):
    alert = _make_alert(
        enriched_event,
        rule_id="DET-01",
        severity="high",
        reason="test reason",
        confidence=0.95,
        recommended_action="test action",
    )

    alert_uuid = uuid.UUID(alert["alert_id"], version=4)
    assert str(alert_uuid) == alert["alert_id"]
    assert alert_uuid.version == 4


def test_make_alert_timestamp_is_iso8601_with_timezone(enriched_event):
    alert = _make_alert(
        enriched_event,
        rule_id="DET-01",
        severity="high",
        reason="test reason",
        confidence=0.95,
        recommended_action="test action",
    )

    assert isinstance(alert["timestamp"], str)
    assert "+" in alert["timestamp"] or "Z" in alert["timestamp"]


def test_load_tor_exit_nodes_from_fixture_file():
    tor_exit_nodes = load_tor_exit_nodes("data/tor-exit-nodes.txt")

    assert isinstance(tor_exit_nodes, frozenset)
    assert len(tor_exit_nodes) >= 3
    assert "185.220.101.1" in tor_exit_nodes


def test_load_tor_exit_nodes_missing_file_returns_empty():
    tor_exit_nodes = load_tor_exit_nodes("nonexistent_path.txt")

    assert tor_exit_nodes == frozenset()


def test_process_key_known_process(enriched_event):
    assert _process_key(enriched_event) == "chrome.exe"


def test_process_key_unknown_process_uses_pid():
    event = {"process_name": "unknown process", "pid": 1234}

    assert _process_key(event) == "unknown_process_1234"


def test_update_connection_rate_counts_and_evicts_old_entries(
    detector_state, monkeypatch
):
    monotonic_values = iter([10.0, 20.0, 79.0])

    monkeypatch.setattr(
        "pnpg.pipeline.detector.time.monotonic",
        lambda: next(monotonic_values),
    )

    config = {"connection_rate_threshold_per_min": 100}
    process_key = "chrome.exe"

    assert _update_connection_rate(process_key, detector_state, config) == 1
    assert _update_connection_rate(process_key, detector_state, config) == 2
    assert _update_connection_rate(process_key, detector_state, config) == 2
    assert detector_state.connection_timestamps[process_key] == [20.0, 79.0]


def test_default_config_includes_connection_rate_threshold_per_min():
    assert DEFAULT_CONFIG["connection_rate_threshold_per_min"] == 100


def test_default_config_includes_tor_exit_list_path():
    assert DEFAULT_CONFIG["tor_exit_list_path"] == "data/tor-exit-nodes.txt"


def test_default_config_includes_known_processes():
    assert isinstance(DEFAULT_CONFIG["known_processes"], list)


def test_rule_det01_unknown_domain_fires_on_public_ip_without_dns(
    detector_state, enriched_event
):
    event = {**enriched_event, "dst_hostname": enriched_event["dst_ip"]}

    alert = rule_det01_unknown_domain(event, DEFAULT_CONFIG, detector_state)

    assert alert is not None
    assert alert["rule_id"] == "DET-01"
    assert alert["severity"] == "WARNING"


def test_rule_det01_unknown_domain_does_not_fire_when_dns_resolves(
    detector_state, enriched_event
):
    alert = rule_det01_unknown_domain(enriched_event, DEFAULT_CONFIG, detector_state)

    assert alert is None


def test_rule_det01_unknown_domain_does_not_fire_on_private_ip(
    detector_state, enriched_event
):
    event = {
        **enriched_event,
        "dst_ip": "192.168.1.1",
        "dst_hostname": "192.168.1.1",
    }

    alert = rule_det01_unknown_domain(event, DEFAULT_CONFIG, detector_state)

    assert alert is None


def test_rule_det02_rate_spike_fires_above_threshold(
    detector_state, enriched_event, monkeypatch
):
    monotonic_values = iter(i * 0.1 for i in range(101))
    monkeypatch.setattr(
        "pnpg.pipeline.detector.time.monotonic",
        lambda: next(monotonic_values),
    )

    alert = None
    for _ in range(101):
        alert = rule_det02_rate_spike(enriched_event, DEFAULT_CONFIG, detector_state)

    assert alert is not None
    assert alert["rule_id"] == "DET-02"
    assert alert["severity"] == "HIGH"


def test_rule_det02_rate_spike_does_not_fire_at_exact_threshold(
    detector_state, enriched_event, monkeypatch
):
    monotonic_values = iter(i * 0.1 for i in range(100))
    monkeypatch.setattr(
        "pnpg.pipeline.detector.time.monotonic",
        lambda: next(monotonic_values),
    )

    alert = None
    for _ in range(100):
        alert = rule_det02_rate_spike(enriched_event, DEFAULT_CONFIG, detector_state)

    assert alert is None


def test_rule_det03_unusual_port_fires_for_unknown_process(detector_state):
    event = {
        "process_name": "unknown process",
        "pid": 1234,
        "dst_ip": "93.184.216.34",
        "dst_hostname": "example.com",
        "dst_port": 9999,
    }

    alert = rule_det03_unusual_port(event, DEFAULT_CONFIG, detector_state)

    assert alert is not None
    assert alert["rule_id"] == "DET-03"
    assert alert["severity"] == "WARNING"


def test_rule_det03_unusual_port_does_not_fire_for_known_process_at_normal_rate(
    detector_state, enriched_event
):
    event = {**enriched_event, "dst_port": 9999}

    alert = rule_det03_unusual_port(event, DEFAULT_CONFIG, detector_state)

    assert alert is None


def test_rule_det04_unknown_process_fires(detector_state):
    event = {
        "process_name": "unknown process",
        "pid": 4321,
        "dst_ip": "93.184.216.34",
    }

    alert = rule_det04_unknown_process(event, DEFAULT_CONFIG, detector_state)

    assert alert is not None
    assert alert["rule_id"] == "DET-04"
    assert alert["severity"] == "ALERT"


def test_rule_det04_unknown_process_does_not_fire_for_known_process(
    detector_state, enriched_event
):
    alert = rule_det04_unknown_process(enriched_event, DEFAULT_CONFIG, detector_state)

    assert alert is None


def test_rule_det05_blocklisted_fires(detector_state, enriched_event):
    event = {
        **enriched_event,
        "threat_intel": {"is_blocklisted": True, "source": "ipsum"},
    }

    alert = rule_det05_blocklisted(event, DEFAULT_CONFIG, detector_state)

    assert alert is not None
    assert alert["rule_id"] == "DET-05"
    assert alert["severity"] == "CRITICAL"


def test_rule_det05_blocklisted_does_not_fire_when_false(
    detector_state, enriched_event
):
    alert = rule_det05_blocklisted(enriched_event, DEFAULT_CONFIG, detector_state)

    assert alert is None


def test_rule_det06_tor_exit_node_fires(detector_state, enriched_event):
    detector_state.tor_exit_nodes = frozenset({enriched_event["dst_ip"]})

    alert = rule_det06_tor_exit_node(enriched_event, DEFAULT_CONFIG, detector_state)

    assert alert is not None
    assert alert["rule_id"] == "DET-06"
    assert alert["severity"] == "HIGH"


def test_rule_det06_tor_exit_node_does_not_fire_when_not_listed(
    detector_state, enriched_event
):
    detector_state.tor_exit_nodes = frozenset({"185.220.101.1"})

    alert = rule_det06_tor_exit_node(enriched_event, DEFAULT_CONFIG, detector_state)

    assert alert is None


def test_rule_det07_new_destination_fires_on_first_connection(
    detector_state, enriched_event
):
    alert = rule_det07_new_destination(enriched_event, DEFAULT_CONFIG, detector_state)

    assert alert is not None
    assert alert["rule_id"] == "DET-07"
    assert alert["severity"] == "LOW"


def test_rule_det07_new_destination_does_not_fire_on_repeat(
    detector_state, enriched_event
):
    first_alert = rule_det07_new_destination(enriched_event, DEFAULT_CONFIG, detector_state)
    second_alert = rule_det07_new_destination(
        enriched_event,
        DEFAULT_CONFIG,
        detector_state,
    )

    assert first_alert is not None
    assert second_alert is None


def test_is_allowlisted_process_scoped_rule_matches(detector_state, enriched_event):
    detector_state.allowlist = [
        {
            "process_name": "chrome.exe",
            "dst_ip": "93.184.216.34",
            "dst_hostname": None,
            "expires_at": None,
        }
    ]

    assert _is_allowlisted(enriched_event, detector_state) is True


def test_is_allowlisted_global_rule_matches(detector_state, enriched_event):
    detector_state.allowlist = [
        {
            "process_name": None,
            "dst_ip": None,
            "dst_hostname": "example.com",
            "expires_at": None,
        }
    ]

    assert _is_allowlisted(enriched_event, detector_state) is True


def test_is_allowlisted_returns_false_for_expired_rule(detector_state, enriched_event):
    detector_state.allowlist = [
        {
            "process_name": "chrome.exe",
            "dst_ip": "93.184.216.34",
            "dst_hostname": None,
            "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
        }
    ]

    assert _is_allowlisted(enriched_event, detector_state) is False


def test_is_allowlisted_returns_false_when_no_rule_matches(
    detector_state, enriched_event
):
    detector_state.allowlist = [
        {
            "process_name": "firefox.exe",
            "dst_ip": "1.1.1.1",
            "dst_hostname": "one.one.one.one",
            "expires_at": None,
        }
    ]

    assert _is_allowlisted(enriched_event, detector_state) is False


def test_is_rate_limited_returns_false_on_first_call(detector_state, monkeypatch):
    monkeypatch.setattr("pnpg.pipeline.detector.time.monotonic", lambda: 10.0)

    is_limited = _is_rate_limited("DET-05", "chrome.exe", detector_state, DEFAULT_CONFIG)

    assert is_limited is False
    assert detector_state.rate_limiter[("DET-05", "chrome.exe")] == 10.0


def test_is_rate_limited_returns_true_on_immediate_second_call(
    detector_state, monkeypatch
):
    monotonic_values = iter([10.0, 10.5])
    monkeypatch.setattr(
        "pnpg.pipeline.detector.time.monotonic",
        lambda: next(monotonic_values),
    )

    first = _is_rate_limited("DET-05", "chrome.exe", detector_state, DEFAULT_CONFIG)
    second = _is_rate_limited("DET-05", "chrome.exe", detector_state, DEFAULT_CONFIG)

    assert first is False
    assert second is True


@pytest.mark.asyncio
async def test_detect_event_returns_empty_list_for_benign_event(
    detector_state, enriched_event
):
    event = {
        **enriched_event,
        "dst_ip": "192.168.1.1",
        "dst_hostname": "router.local",
    }
    detector_state.first_seen["chrome.exe"] = {"192.168.1.1"}

    alerts = await detect_event(event, DEFAULT_CONFIG, detector_state)

    assert alerts == []


@pytest.mark.asyncio
async def test_detect_event_returns_det05_for_blocklisted_event(
    detector_state, enriched_event, monkeypatch
):
    monotonic_values = itertools.chain([10.0, 10.1], itertools.repeat(10.1))
    monkeypatch.setattr(
        "pnpg.pipeline.detector.time.monotonic",
        lambda: next(monotonic_values),
    )
    detector_state.first_seen["chrome.exe"] = {enriched_event["dst_ip"]}
    event = {
        **enriched_event,
        "threat_intel": {"is_blocklisted": True, "source": "ipsum"},
    }

    alerts = await detect_event(event, DEFAULT_CONFIG, detector_state)

    assert len(alerts) == 1
    assert alerts[0]["rule_id"] == "DET-05"
    assert alerts[0]["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_detect_event_allowlist_suppresses_matching_rule(
    detector_state, enriched_event, monkeypatch
):
    monotonic_values = itertools.chain([10.0], itertools.repeat(10.0))
    monkeypatch.setattr(
        "pnpg.pipeline.detector.time.monotonic",
        lambda: next(monotonic_values),
    )
    detector_state.first_seen["chrome.exe"] = {enriched_event["dst_ip"]}
    detector_state.allowlist = [
        {
            "process_name": "chrome.exe",
            "dst_ip": enriched_event["dst_ip"],
            "dst_hostname": None,
            "expires_at": None,
        }
    ]
    event = {
        **enriched_event,
        "threat_intel": {"is_blocklisted": True, "source": "ipsum"},
    }

    alerts = await detect_event(event, DEFAULT_CONFIG, detector_state)

    assert alerts == []


@pytest.mark.asyncio
async def test_detect_event_rate_limiter_suppresses_second_rapid_alert(
    detector_state, enriched_event, monkeypatch
):
    monotonic_values = itertools.chain([10.0, 10.1, 10.2, 10.3], itertools.repeat(10.3))
    monkeypatch.setattr(
        "pnpg.pipeline.detector.time.monotonic",
        lambda: next(monotonic_values),
    )
    detector_state.first_seen["chrome.exe"] = {enriched_event["dst_ip"]}
    event = {
        **enriched_event,
        "threat_intel": {"is_blocklisted": True, "source": "ipsum"},
    }

    first_alerts = await detect_event(event, DEFAULT_CONFIG, detector_state)
    second_alerts = await detect_event(event, DEFAULT_CONFIG, detector_state)

    assert len(first_alerts) == 1
    assert first_alerts[0]["rule_id"] == "DET-05"
    assert second_alerts == []


@pytest.mark.asyncio
async def test_detect_event_suppresses_rule_for_process(
    detector_state, enriched_event, monkeypatch
):
    monkeypatch.setattr("pnpg.pipeline.detector.time.monotonic", lambda: 10.0)
    detector_state.first_seen["chrome.exe"] = {enriched_event["dst_ip"]}
    detector_state.suppressed_rules.add(("DET-05", "chrome.exe"))
    event = {
        **enriched_event,
        "threat_intel": {"is_blocklisted": True, "source": "ipsum"},
    }

    alerts = await detect_event(event, DEFAULT_CONFIG, detector_state)

    assert alerts == []
