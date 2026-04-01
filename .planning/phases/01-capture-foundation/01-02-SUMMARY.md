---
phase: 01-capture-foundation
plan: "02"
subsystem: capture
tags: [scapy, asyncio, queue-bridge, drop-head, interface-selection, threading, tdd]
dependency_graph:
  requires: [01-01]
  provides: [pnpg.capture.queue_bridge, pnpg.capture.interface, pnpg.capture.sniffer]
  affects: [pipeline-worker, main-lifespan]
tech_stack:
  added: []
  patterns:
    - "call_soon_threadsafe for thread-to-asyncio bridge (CAP-05)"
    - "drop-head eviction with get_nowait()+put_nowait() (CAP-06)"
    - "dual ISO8601+monotonic timestamps per packet event (CAP-08)"
    - "_get_scapy_ifaces() isolator for testable Scapy import (Windows)"
    - "mutable list as counter in closure [drop_counter[0]] pattern"
key_files:
  created:
    - pnpg/capture/__init__.py
    - pnpg/capture/queue_bridge.py
    - pnpg/capture/interface.py
    - pnpg/capture/sniffer.py
    - tests/test_capture/__init__.py
    - tests/test_capture/test_queue_bridge.py
    - tests/test_capture/test_interface.py
  modified: []
decisions:
  - "Isolated Scapy import behind _get_scapy_ifaces() helper in interface.py so tests can mock it without Npcap installed"
  - "drop_counter is a single-element list [int] so mutable state works correctly in Python closures"
  - "sniffer.py implements start_sniffer() as a simple single-run starter; supervisor coroutine (CAP-10) is deferred to Plan 03"
metrics:
  duration_seconds: 138
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_created: 7
  files_modified: 0
requirements: [CAP-01, CAP-04, CAP-05, CAP-06, CAP-07, CAP-08, CAP-09, TEST-01]
---

# Phase 01 Plan 02: Capture Pipeline — Queue Bridge, Interface Selector, Sniffer Summary

**One-liner:** Scapy sniffer daemon thread feeding packets via call_soon_threadsafe into a bounded asyncio.Queue with drop-head eviction, ISO8601+monotonic dual timestamps, and psutil-driven interface auto-selection.

## What Was Built

The core capture pipeline that moves packets from Scapy's blocking daemon thread into the asyncio event loop safely and efficiently.

### pnpg/capture/queue_bridge.py
Implements the thread-to-asyncio bridge (CAP-05/06/07/08):
- `make_packet_event(pkt)` — creates event dict with UTC ISO8601 timestamp and monotonic float
- `_enqueue_packet(queue, drop_counter, pkt)` — runs in event loop thread via call_soon_threadsafe; implements drop-head eviction when queue is full and logs each drop as INFO
- `make_packet_handler(loop, queue, drop_counter)` — returns Scapy prn= callback that bridges the daemon thread to the event loop

### pnpg/capture/interface.py
Implements interface auto-selection and override (CAP-04/09):
- `select_interface(config)` — returns config override immediately if set; otherwise queries psutil.net_io_counters(pernic=True), selects highest bytes_sent interface, then attempts psutil-friendly-name → Scapy GUID mapping via conf.ifaces.dev_from_networkname()
- `_get_scapy_ifaces()` — isolates Scapy import for testability (Scapy requires Npcap to import on Windows)

### pnpg/capture/sniffer.py
Implements the daemon thread sniffer (CAP-01):
- `start_sniffer(iface, packet_handler, stop_event)` — creates and starts daemon thread running Scapy sniff() with store=False, filter="ip", stop_filter on stop_event
- `_sniffer_target()` — catches all exceptions and logs at CRITICAL (SYS-01/CONFIG-03)

## Tests

All 8 tests in tests/test_capture/ pass GREEN:
- `test_queue_maxsize` — asyncio.Queue(maxsize=N) respected
- `test_drop_head` — oldest item evicted when full
- `test_drop_log` — INFO log with "Packet dropped" text on eviction
- `test_timestamps` — event dict has ISO8601 timestamp and monotonic float
- `test_packet_handler_calls_threadsafe` — call_soon_threadsafe called exactly once with correct args
- `test_auto_select_highest_bytes_sent` — psutil queried, highest bytes_sent selected
- `test_config_override` — psutil NOT called when config['interface'] is set
- `test_no_interfaces_raises` — RuntimeError raised on empty psutil result

Full test suite: 16/16 pass (8 new + 8 from Plan 01).

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| `_get_scapy_ifaces()` isolator | Scapy's `from scapy.config import conf` fails on Windows without Npcap. Isolating it behind a helper function lets tests mock it cleanly without requiring Npcap in CI. |
| `drop_counter` as `list[int]` | Python closures capture variables by reference but ints are immutable. A single-element list `[0]` allows `_enqueue_packet` to mutate the counter that `make_packet_handler` holds a reference to. |
| `start_sniffer` is single-run only | The supervisor coroutine (CAP-10, exponential backoff restart) is deferred to Plan 03 per the plan structure. `start_sniffer` starts the thread once; the supervisor owns restart logic. |

## Deviations from Plan

### Auto-added: _get_scapy_ifaces() helper

**Rule 2 - Missing critical functionality**
- **Found during:** Task 2 implementation
- **Issue:** The plan's interface.py code imported `from scapy.config import conf` at the function body level inside a try/except. On Windows without Npcap installed, this import succeeds at the Python level but `conf.ifaces` may be incomplete. More critically, tests cannot mock `conf.ifaces` without an actual Scapy import. This would have caused all `test_auto_select_highest_bytes_sent` tests to fail without Npcap.
- **Fix:** Isolated the Scapy import into `_get_scapy_ifaces()` so tests can mock `pnpg.capture.interface._get_scapy_ifaces` directly.
- **Files modified:** `pnpg/capture/interface.py`, `tests/test_capture/test_interface.py`
- **Commit:** 9641e4f

## Known Stubs

None. All implemented functionality is fully wired. `raw_pkt` in packet events intentionally stores the Scapy packet object — this is consumed by Plan 03 (process mapping) which enriches it.

## Self-Check: PASSED

All 7 files created and verified. Commits 2f6e660 (test RED) and 9641e4f (feat GREEN) confirmed in git log.
