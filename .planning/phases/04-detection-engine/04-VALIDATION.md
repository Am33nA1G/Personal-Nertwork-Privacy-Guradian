---
phase: 4
slug: detection-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-05
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `tests/conftest.py` (existing) |
| **Quick run command** | `pytest tests/test_pipeline/test_detector.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_pipeline/test_detector.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | DET-01 | unit | `pytest tests/test_pipeline/test_detector.py::test_det01_unknown_domain -x -q` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 1 | DET-02 | unit | `pytest tests/test_pipeline/test_detector.py::test_det02_rate_spike -x -q` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 1 | DET-03 | unit | `pytest tests/test_pipeline/test_detector.py::test_det03_unusual_port -x -q` | ❌ W0 | ⬜ pending |
| 4-01-04 | 01 | 1 | DET-04 | unit | `pytest tests/test_pipeline/test_detector.py::test_det04_unknown_process -x -q` | ❌ W0 | ⬜ pending |
| 4-01-05 | 01 | 1 | DET-05 | unit | `pytest tests/test_pipeline/test_detector.py::test_det05_blocklisted_ip -x -q` | ❌ W0 | ⬜ pending |
| 4-01-06 | 01 | 1 | DET-06 | unit | `pytest tests/test_pipeline/test_detector.py::test_det06_tor_exit_node -x -q` | ❌ W0 | ⬜ pending |
| 4-01-07 | 01 | 1 | DET-07 | unit | `pytest tests/test_pipeline/test_detector.py::test_det07_new_destination -x -q` | ❌ W0 | ⬜ pending |
| 4-01-08 | 01 | 1 | DET-08 | unit | `pytest tests/test_pipeline/test_detector.py::test_det08_config_constants -x -q` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 2 | DET-09 | unit | `pytest tests/test_pipeline/test_detector.py::test_det09_rate_limiter -x -q` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 2 | DET-10 | unit | `pytest tests/test_pipeline/test_detector.py::test_det10_alert_object -x -q` | ❌ W0 | ⬜ pending |
| 4-02-03 | 02 | 2 | ALLOW-01,02,03,04 | unit | `pytest tests/test_pipeline/test_detector.py::test_allowlist_suppression -x -q` | ❌ W0 | ⬜ pending |
| 4-02-04 | 02 | 2 | SUPP-01,02 | unit | `pytest tests/test_pipeline/test_detector.py::test_suppression_store -x -q` | ❌ W0 | ⬜ pending |
| 4-02-05 | 02 | 2 | DET-01..DET-10 | integration | `pytest tests/test_pipeline/test_detector.py::test_pipeline_integration -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline/test_detector.py` — stubs for DET-01 to DET-10, ALLOW-01 to ALLOW-04, SUPP-01, SUPP-02
- [ ] `tests/conftest.py` — add `detector_state` and `enriched_event` fixtures
- [ ] `config.yaml` — add detection threshold constants (connection_rate_threshold_per_min, unusual_ports list, known_processes list, alert_rate_limit_per_sec)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DET-03 false-positive gate confirmed | DET-03 | Requires live traffic with known process baseline | Send 50 connections on port 8080 from a whitelisted process; verify no alert emitted |
| Rate limiter confirmed by log count | DET-09 | Requires time-based log inspection | Run 10 rapid events for same rule+process; verify log shows exactly 1 alert per second |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
