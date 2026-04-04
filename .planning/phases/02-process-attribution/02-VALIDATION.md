---
phase: 2
slug: process-attribution
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `pytest.ini` (asyncio_mode = auto, testpaths = tests) |
| **Quick run command** | `python -m pytest tests/test_pipeline/ tests/test_capture/ -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -q --tb=short`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green (23 baseline + new Phase 2 tests)
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 02-01 | 0 | PROC-01–06, D-01–03 | unit | `python -m pytest tests/test_pipeline/test_process_mapper.py tests/test_capture/test_queue_bridge.py -x -q` | ❌ W0 | ⬜ pending |
| 2-01-02 | 02-01 | 1 | PROC-02 | unit | `python -m pytest tests/test_pipeline/test_process_mapper.py::test_poller_interval -x -q` | ❌ W0 | ⬜ pending |
| 2-01-03 | 02-01 | 1 | PROC-06 | unit | `python -m pytest tests/test_pipeline/test_process_mapper.py::test_ttl_expiry -x -q` | ❌ W0 | ⬜ pending |
| 2-01-04 | 02-01 | 1 | PROC-03, PROC-04 | unit | `python -m pytest tests/test_pipeline/test_process_mapper.py::test_cache_miss tests/test_pipeline/test_process_mapper.py::test_access_denied -x -q` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02-02 | 1 | D-01, D-02, D-03 | unit | `python -m pytest tests/test_capture/test_queue_bridge.py -x -q` | ✅ (modify) | ⬜ pending |
| 2-02-02 | 02-02 | 1 | PROC-01, PROC-05 | unit | `python -m pytest tests/test_pipeline/test_process_mapper.py::test_key_lookup -x -q` | ❌ W0 | ⬜ pending |
| 2-02-03 | 02-02 | 2 | All PROC + D | integration | `python -m pytest tests/ -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline/test_process_mapper.py` — stub test file covering PROC-01 through PROC-06 (new file — must exist before implementation begins)
- [ ] `tests/test_capture/test_queue_bridge.py` — add D-01/D-02/D-03 test cases for field extraction and raw_pkt debug flag (modify existing file)

*Existing infrastructure covers all other needs — pytest.ini already configured with asyncio_mode = auto. No new framework config needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| psutil.net_connections() called on 200ms schedule confirmed by log timestamps | PROC-02 | Timing precision requires log inspection | Run app, observe log output, confirm `[process_mapper] poll` entries appear ~200ms apart |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
