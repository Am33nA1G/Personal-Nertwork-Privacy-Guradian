---
phase: 02-process-attribution
verified: 2026-04-01T00:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Run the full application under live traffic and confirm process names appear in console output"
    expected: "Pipeline events printed at DEBUG level show non-empty process_name (e.g., chrome.exe) and pid > 0 for active connections"
    why_human: "Cannot invoke the Scapy sniffer without Npcap and admin privileges in CI; psutil attribution of live connections requires a real OS environment"
---

# Phase 2: Process Attribution — Verification Report

**Phase Goal:** Every packet event in the queue is annotated with the originating process name and PID using a proactive psutil polling cache; unattributable connections degrade gracefully to "unknown process"
**Verified:** 2026-04-01
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Each connection event carries a process name and PID field visible in pipeline output | VERIFIED | `enrich_event()` adds `process_name` and `pid` to every event dict; `pipeline_worker` calls `enrich_event` on each dequeued event; `debug_mode=True` logs the enriched event via `logger.debug("PIPELINE EVENT: %s", event)` |
| 2 | System processes (AccessDenied) show "unknown process" and PID -1 without crashing | VERIFIED | `_refresh_cache` catches `psutil.AccessDenied` from both `net_connections()` and `Process(pid).name()`; sets `process_name="unknown process"`, `pid=-1`; test `test_access_denied_net_connections` and `test_access_denied_process_name` both pass |
| 3 | Short-lived connections that disappear before cache update show "unknown process" | VERIFIED | `enrich_event` returns `"unknown process" / pid=-1` on any cache miss; ICMP events with `src_port=None` naturally produce cache misses via `(src_ip, None)` key lookup; D-03 test passes |
| 4 | psutil.net_connections() is called on 200ms background schedule, never per-packet | VERIFIED | `process_poller_loop` is a standalone asyncio task calling `_refresh_cache` then `asyncio.sleep(interval)`; `interval = config.get("poll_interval_ms", 200) / 1000.0`; `enrich_event` performs only a dict key lookup (no psutil call); `test_poller_interval` verifies sleep arg is `0.2` |
| 5 | Cache entries expire after configured TTL (default 2 seconds) | VERIFIED | Each cache entry carries `"expires_at": time.monotonic() + ttl_secs`; `enrich_event` checks `time.monotonic() < entry["expires_at"]` before returning cached values; `proc_cache_ttl_sec: 2` is in `DEFAULT_CONFIG`; `test_ttl_expiry` and `test_ttl_valid` both pass |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pnpg/pipeline/process_mapper.py` | TTL-expiring cache, background poller, enrich function | VERIFIED | 163 lines; exports `_refresh_cache`, `process_poller_loop`, `enrich_event`; all three are substantively implemented with full psutil error handling |
| `pnpg/capture/queue_bridge.py` | D-01/D-02/D-03 field extraction in `make_packet_event` | VERIFIED | Extracts `src_ip`, `dst_ip`, `src_port`, `dst_port`, `protocol` from IP/TCP/UDP layers; `raw_pkt` gated on `debug_mode`; None ports for ICMP |
| `pnpg/pipeline/worker.py` | `enrich_event` wired at Phase 2 stub location | VERIFIED | Line 14 imports `enrich_event`; line 55 calls `enrich_event(event, process_cache)` in the worker loop |
| `pnpg/main.py` | `process_cache` dict, `process_poller_loop` asyncio task, cache passed to worker | VERIFIED | Line 86: `process_cache: dict = {}`; line 88: `asyncio.create_task(process_poller_loop(process_cache, config))`; line 94: `pipeline_worker(queue, config, process_cache)`; poller cancelled before worker in shutdown |
| `pnpg/config.py` | `poll_interval_ms: 200` and `proc_cache_ttl_sec: 2` in DEFAULT_CONFIG | VERIFIED | Both keys present at lines 16 and 25 |
| `tests/test_pipeline/test_process_mapper.py` | 10 tests covering PROC-01 through PROC-06 | VERIFIED | 10 tests present; all 10 pass |
| `tests/test_capture/test_queue_bridge.py` | 6 D-series tests (D-01/D-02/D-03) + 5 original | VERIFIED | All 11 tests pass; D-series tests cover TCP, UDP, ICMP, debug_mode on/off, no-IP-layer cases |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `make_packet_event()` in queue_bridge.py | `src_ip`, `src_port`, `dst_ip`, `dst_port`, `protocol` fields in event | `pkt.haslayer("IP"/"TCP"/"UDP")` conditionals | WIRED | Fields extracted and present in returned event dict |
| `process_poller_loop` in main.py | `process_cache` dict (shared reference) | `asyncio.create_task` + same dict reference passed to worker | WIRED | Cache dict created once, passed to both poller and worker; poller mutates in-place via `cache.clear()+cache.update()` |
| `pipeline_worker` | `enrich_event` | `from pnpg.pipeline.process_mapper import enrich_event`; called as `event = enrich_event(event, process_cache)` | WIRED | Import at line 14; call at line 55; result assigned back to `event` for downstream stages |
| `_refresh_cache` | psutil connection table | `psutil.net_connections(kind="inet")` + `psutil.Process(pid).name()` | WIRED | Both psutil calls present; results stored into `new_cache` dict; `AccessDenied` caught on both paths |
| `enrich_event` | TTL check | `time.monotonic() < entry["expires_at"]` | WIRED | Lazy expiry check on every cache read; stale entries fall through to `"unknown process"` |
| Shutdown sequence | Poller cancelled before worker | `poller_task.cancel()` before `worker_task.cancel()` in lifespan | WIRED | Lines 119-125 cancel and await poller; lines 125-135 cancel and await worker |

---

### Data-Flow Trace (Level 4)

These artifacts enrich data but do not render UI — data flow is through the asyncio pipeline, not to a browser. The enriched event dict is the output.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `enrich_event()` | `process_name`, `pid` | `process_cache` dict populated by `_refresh_cache` | Yes — `psutil.net_connections()` reads OS connection table | FLOWING |
| `_refresh_cache()` | `new_cache` | `psutil.net_connections(kind="inet")` | Yes — live OS call; degrades gracefully on AccessDenied | FLOWING |
| `process_poller_loop()` | (drives cache refresh) | `asyncio.sleep(0.2)` + `_refresh_cache` call | Yes — timed loop with real psutil call | FLOWING |
| `make_packet_event()` | `src_ip`, `src_port`, `dst_ip`, `dst_port`, `protocol` | Scapy packet layers | Yes — extracted from real packet headers via `pkt.haslayer()` | FLOWING |

---

### Behavioral Spot-Checks

The sniffer requires Npcap and admin privileges — live packet capture cannot be tested without a real OS environment. Isolated module tests run instead.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 39 tests pass (Phase 1 + Phase 2) | `python -m pytest tests/ -q --tb=short` | `39 passed in 0.21s` | PASS |
| `enrich_event` defined in process_mapper | `grep -n "def enrich_event" pnpg/pipeline/process_mapper.py` | Line 135 | PASS |
| `process_poller_loop` imported and started in main.py | `grep -n "process_poller_loop" pnpg/main.py` | Lines 25, 88 | PASS |
| `process_cache` created and passed to worker | `grep -n "process_cache" pnpg/main.py` | Lines 86, 88, 94, 103 | PASS |
| `haslayer` called for D-01 field extraction | `grep -n "haslayer" pnpg/capture/queue_bridge.py` | Lines 61, 67, 70 | PASS |
| `debug_mode` gates `raw_pkt` inclusion (D-02) | `grep -n "debug_mode" pnpg/capture/queue_bridge.py` | Line 75 | PASS |

---

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| PROC-01 | System maps each connection to process name and PID using psutil | SATISFIED | `enrich_event()` adds `process_name` + `pid` to every event; cache populated from `psutil.net_connections()` |
| PROC-02 | psutil polled on 200ms background schedule — not per-packet | SATISFIED | `process_poller_loop` asyncio task with `asyncio.sleep(poll_interval_ms/1000)`; `poll_interval_ms=200` in DEFAULT_CONFIG; `enrich_event` does zero psutil calls |
| PROC-03 | Unattributable connections show "unknown process" without failing | SATISFIED | Cache miss path and expired-entry path both return `{"process_name": "unknown process", "pid": -1}` |
| PROC-04 | AccessDenied from psutil handled gracefully | SATISFIED | `_refresh_cache` catches `psutil.AccessDenied` on `net_connections()` (leaves cache intact) and on `Process(pid).name()` (stores `"unknown process"`) |
| PROC-05 | Correlation via (src_ip, src_port) lookup cache | SATISFIED | Cache key is `(conn.laddr.ip, conn.laddr.port)`; lookup key in `enrich_event` is `(event.get("src_ip"), event.get("src_port"))` |
| PROC-06 | Cache entries expire after configurable TTL (default 2s) | SATISFIED | `expires_at = time.monotonic() + ttl_secs`; lazy check in `enrich_event`; `proc_cache_ttl_sec: 2` in DEFAULT_CONFIG |

All 6 Phase 2 requirements: SATISFIED.

---

### Anti-Patterns Found

No blockers or warnings found.

| File | Pattern | Severity | Verdict |
|------|---------|----------|---------|
| `worker.py` lines 58-61 | Phase 3-5 stub comments | Info | Intentional — documented in SUMMARY; not code stubs, only comments marking future injection points |
| `process_mapper.py` line 99 | `cache.clear()` before `cache.update()` | Info | Intentional — atomic in-place replacement pattern to preserve shared dict reference; documented in module docstring |

No TODO/FIXME/HACK/placeholder patterns found in Phase 2 implementation files. No `return null`, `return {}`, `return []` stubs in production paths. All event enrichment returns meaningful dicts.

---

### Human Verification Required

#### 1. Live Process Attribution

**Test:** Start the application as Administrator on Windows with Npcap installed, open a browser and navigate to any HTTPS site, observe the console DEBUG output with `debug_mode: true` in config.yaml.
**Expected:** Pipeline events show `process_name` as the browser process (e.g., `chrome.exe`, `msedge.exe`) and a positive integer `pid` matching the browser PID visible in Task Manager.
**Why human:** Requires Npcap driver, administrator privileges, and a real network interface — cannot be replicated in a sandboxed test environment.

---

### Gaps Summary

No gaps. All five observable truths are verified, all six requirements are satisfied, all artifacts are substantive and wired, and data flows through the pipeline from psutil to the enriched event dict.

The only outstanding item is a human smoke-test of live process attribution, which requires a real Windows environment with admin privileges and Npcap installed. This does not block Phase 3 from starting — the code contract (event schema with `process_name` and `pid`) is fully implemented and tested.

---

_Verified: 2026-04-01_
_Verifier: Claude (gsd-verifier)_
