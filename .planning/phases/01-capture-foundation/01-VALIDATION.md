---
phase: 1
slug: capture-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-31
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pytest.ini` (Wave 0 gap — does not exist yet) |
| **Quick run command** | `python -m pytest tests/test_capture/ tests/test_pipeline/ tests/test_config.py tests/test_prereqs.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_capture/ tests/test_pipeline/ tests/test_config.py tests/test_prereqs.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01-01 | 0 | CAP-02 | unit | `pytest tests/test_prereqs.py::test_npcap_check_exits -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01-01 | 0 | CAP-03 | unit | `pytest tests/test_prereqs.py::test_admin_check_exits -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01-01 | 0 | CONFIG-01, CONFIG-02 | unit | `pytest tests/test_config.py::test_defaults -x` | ❌ W0 | ⬜ pending |
| 1-02-01 | 01-02 | 0 | CAP-04, CAP-09 | unit | `pytest tests/test_capture/test_interface.py::test_config_override -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 01-02 | 0 | CAP-05 | unit | `pytest tests/test_capture/test_queue_bridge.py::test_queue_maxsize -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 01-02 | 0 | CAP-06, CAP-07 | unit | `pytest tests/test_capture/test_queue_bridge.py::test_drop_head -x` | ❌ W0 | ⬜ pending |
| 1-02-04 | 01-02 | 0 | CAP-08 | unit | `pytest tests/test_capture/test_queue_bridge.py::test_timestamps -x` | ❌ W0 | ⬜ pending |
| 1-02-05 | 01-02 | 0 | TEST-01 | unit | `pytest tests/test_pipeline/test_worker.py::test_debug_mode -x` | ❌ W0 | ⬜ pending |
| 1-03-01 | 01-03 | 0 | CAP-10 | unit | `pytest tests/test_capture/test_sniffer.py::test_supervisor_restart -x` | ❌ W0 | ⬜ pending |
| 1-03-02 | 01-03 | 0 | PIPE-01, PIPE-02 | unit | `pytest tests/test_pipeline/test_worker.py::test_consumes_queue -x` | ❌ W0 | ⬜ pending |
| 1-03-03 | 01-03 | 0 | CONFIG-03, SYS-01 | unit | `pytest tests/test_pipeline/test_worker.py::test_error_no_crash -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — makes tests a package
- [ ] `tests/conftest.py` — shared fixtures (mock sniff, mock queue)
- [ ] `tests/test_prereqs.py` — stubs for CAP-02, CAP-03
- [ ] `tests/test_config.py` — stubs for CONFIG-01, CONFIG-02
- [ ] `tests/test_capture/__init__.py`
- [ ] `tests/test_capture/test_queue_bridge.py` — stubs for CAP-05, CAP-06, CAP-07, CAP-08
- [ ] `tests/test_capture/test_interface.py` — stubs for CAP-04, CAP-09
- [ ] `tests/test_capture/test_sniffer.py` — stubs for CAP-10 (mock `sniff()`)
- [ ] `tests/test_pipeline/__init__.py`
- [ ] `tests/test_pipeline/test_worker.py` — stubs for PIPE-01, PIPE-02, CONFIG-03/SYS-01, TEST-01
- [ ] `pytest.ini` — `asyncio_mode = auto` for pytest-asyncio
- [ ] Framework install: `pip install pytest>=8.0.0 pytest-asyncio>=0.23.0`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Packets visible in queue within 5s of startup | CAP-01 | Requires Npcap + admin + live network | Run app as admin after Npcap install; observe queue log output within 5s |
| Interface auto-selection picks highest-traffic NIC | CAP-04 | Requires live Npcap environment | Run app without interface override; verify selected interface in startup log |
| psutil→Scapy GUID name mapping resolves correctly | CAP-04 | Requires Npcap installed to test | Run `python -c "from scapy.all import conf; print(conf.ifaces)"` after Npcap install |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
