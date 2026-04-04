---
phase: 02-process-attribution
plan: "01"
subsystem: pipeline
tags: [process-mapper, psutil, cache, asyncio, tdd]
dependency_graph:
  requires:
    - 01-03-PLAN.md  # pipeline_worker, sniffer_supervisor, main.py lifespan
  provides:
    - pnpg/pipeline/process_mapper.py  # _refresh_cache, process_poller_loop, enrich_event
  affects:
    - pnpg/pipeline/worker.py  # Plan 02 will wire enrich_event into pipeline_worker
    - pnpg/capture/queue_bridge.py  # Plan 02 will update make_packet_event signature
    - pnpg/main.py  # Plan 02 will start process_poller_loop in lifespan
tech_stack:
  added: []
  patterns:
    - TTL-expiring process cache keyed on (src_ip, src_port) tuple
    - Background asyncio poller task at fixed interval (mirrors sniffer_supervisor pattern)
    - Lazy TTL expiry on cache read (time.monotonic() comparison)
    - Atomic in-place cache mutation via cache.clear() + cache.update()
    - Immutable event enrichment via {**event, new_fields}
key_files:
  created:
    - pnpg/pipeline/process_mapper.py
    - tests/test_pipeline/test_process_mapper.py
  modified:
    - tests/test_capture/test_queue_bridge.py
decisions:
  - Cache atomic mutation uses cache.clear()+cache.update() not reference reassignment to preserve shared dict reference across callers
  - VALID_STATUSES filter (ESTABLISHED/SYN_SENT/CLOSE_WAIT) eliminates 0.0.0.0 laddr mismatch from LISTEN sockets
  - psutil poller runs as pure asyncio task (no thread) — empirically verified at 1.1ms per call on this machine
metrics:
  duration_seconds: 178
  completed_date: "2026-04-04"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 2 Plan 01: Process Mapper — Summary

**One-liner:** TTL-expiring psutil process cache with 200ms asyncio background poller and immutable per-event enrichment via (src_ip, src_port) dict lookup.

## Objective

Build the psutil background poller, TTL-expiring connection cache, and per-event enrichment function. Create all Wave 0 test stubs for both plans (process_mapper tests + queue_bridge D-01/D-02/D-03 tests).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wave 0 — Create all test stubs for Phase 2 | 9afa198 | tests/test_pipeline/test_process_mapper.py (new), tests/test_capture/test_queue_bridge.py (modified) |
| 2 | Implement process_mapper.py — cache, poller, and enrich_event | 4597352 | pnpg/pipeline/process_mapper.py (new) |

## Verification Results

- `python -m pytest tests/test_pipeline/test_process_mapper.py -v` — 10/10 PASSED (PROC-01 through PROC-06)
- `python -m pytest tests/test_config.py tests/test_prereqs.py tests/test_pipeline/test_worker.py -q` — 12/12 PASSED (Phase 1 unbroken)
- `python -m pytest tests/ -q` — 33 passed, 6 expected RED (D-01/D-02/D-03 queue_bridge tests — fixed in Plan 02)

## Deviations from Plan

None — plan executed exactly as written.

The 6 RED tests in `test_queue_bridge.py` (D-01/D-02/D-03) are expected and documented in the plan. They exercise the new `make_packet_event(pkt, config)` signature that Plan 02 will implement.

## Known Stubs

None in process_mapper.py — all three public functions are fully implemented.

The D-01/D-02/D-03 test stubs in `test_queue_bridge.py` are intentional RED stubs for Plan 02 (which updates `make_packet_event()` in `queue_bridge.py`).

## Decisions Made

1. **Cache atomic mutation pattern** — `cache.clear(); cache.update(new_cache)` rather than reassigning the reference. This preserves the shared dict object that `process_poller_loop` and `enrich_event` both hold a reference to (Research Pitfall 5).

2. **VALID_STATUSES filter** — Only ESTABLISHED, SYN_SENT, and CLOSE_WAIT connections enter the cache. This eliminates LISTEN socket entries with `0.0.0.0` / `::` laddr that would pollute the cache and never match actual packet src_ip values (Research Pitfall 2).

3. **Pure asyncio task for poller** — psutil.net_connections() takes ~1.1ms on this machine (empirically verified in RESEARCH.md). No thread executor is needed. The poller runs as a plain `asyncio.create_task()` coroutine identical to the sniffer_supervisor pattern.

## Self-Check: PASSED

Files created:
- FOUND: pnpg/pipeline/process_mapper.py
- FOUND: tests/test_pipeline/test_process_mapper.py
- FOUND: tests/test_capture/test_queue_bridge.py (modified)
- FOUND: .planning/phases/02-process-attribution/02-01-SUMMARY.md

Commits verified:
- 9afa198 — test(02-01): Wave 0 test stubs
- 4597352 — feat(02-01): process_mapper implementation
