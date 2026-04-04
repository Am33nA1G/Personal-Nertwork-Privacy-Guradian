---
phase: 02-process-attribution
plan: "02"
subsystem: pipeline
tags: [queue-bridge, process-mapper, scapy, psutil, asyncio, field-extraction]

requires:
  - phase: 02-01
    provides: "process_mapper.py with enrich_event, process_poller_loop, and TTL cache"
  - phase: 01-03
    provides: "pipeline_worker, sniffer_supervisor, main.py lifespan, queue_bridge"

provides:
  - "make_packet_event(pkt, config) with D-01/D-02/D-03 field extraction"
  - "enrich_event wired into pipeline_worker at Phase 2 stub location"
  - "process_poller_loop started as asyncio task in lifespan"
  - "Full Phase 2 data flow: Scapy packet -> field extraction -> queue -> worker -> process attribution -> enriched event"

affects:
  - "Phase 3 dns-resolution — worker now emits events with process_name, pid, src_ip, src_port, dst_ip, dst_port, protocol"

tech-stack:
  added: []
  patterns:
    - "Signature cascade pattern: config flows from lifespan -> make_packet_handler -> _enqueue_packet -> make_packet_event"
    - "Immutable event enrichment via {**event, ...} — original dict never mutated"
    - "Poller cancelled before worker in shutdown to preserve cache access during queue drain"

key-files:
  created: []
  modified:
    - pnpg/capture/queue_bridge.py
    - pnpg/capture/sniffer.py
    - pnpg/pipeline/worker.py
    - pnpg/main.py
    - tests/test_capture/test_queue_bridge.py
    - tests/test_pipeline/test_worker.py

key-decisions:
  - "Config flows as 4th arg through make_packet_handler -> _enqueue_packet -> make_packet_event rather than using a module-level global — preserves testability and avoids hidden state"
  - "Poller task cancelled before worker task in shutdown sequence — ensures worker can still read cache during queue drain phase"
  - "Worker tests pass empty dict {} as process_cache — enrich_event degrades gracefully to unknown process / pid=-1 on cache miss, which is correct test isolation behavior"

patterns-established:
  - "D-02 debug gate: config.get('debug_mode') controls raw_pkt inclusion — never unconditional"
  - "D-03 fallback: ICMP and other non-TCP/UDP protocols produce None ports without event drop"

requirements-completed: [PROC-01, PROC-02, PROC-03, PROC-05]

duration: 3min
completed: "2026-04-04"
---

# Phase 2 Plan 02: Queue Bridge Wiring and Pipeline Integration — Summary

**Field extraction wired into make_packet_event (D-01/D-02/D-03), enrich_event called in pipeline_worker, and process_poller_loop started in lifespan — completing the full Phase 2 data flow from Scapy packet to enriched event.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-04T07:46:18Z
- **Completed:** 2026-04-04T07:49:20Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Updated `make_packet_event(pkt, config)` to extract 5 IP/TCP/UDP fields per D-01, with conditional raw_pkt per D-02 and None ports for ICMP per D-03
- Signature cascade propagated through `_enqueue_packet`, `make_packet_handler`, and `sniffer_supervisor` — config flows end-to-end without globals
- `pipeline_worker` now accepts `process_cache` as 3rd arg and calls `enrich_event(event, process_cache)` at the former Phase 2 stub location
- `main.py` lifespan creates `process_cache: dict = {}`, starts `process_poller_loop` as asyncio task, passes cache to worker, and cancels poller before worker in shutdown
- All 39 tests GREEN: 11 queue_bridge tests (5 updated + 6 D-series now GREEN), 17 total capture tests, 10 process_mapper tests, 4 worker tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Update make_packet_event and queue_bridge signatures per D-01/D-02/D-03** - `a4cc5a0` (feat)
2. **Task 2: Wire enrich_event into worker, start poller in lifespan, fix worker tests** - `a5c4895` (feat)

## Files Created/Modified

- `pnpg/capture/queue_bridge.py` — make_packet_event now extracts src_ip, src_port, dst_ip, dst_port, protocol; config cascades through all 3 functions
- `pnpg/capture/sniffer.py` — sniffer_supervisor passes config to make_packet_handler
- `pnpg/pipeline/worker.py` — imports enrich_event, accepts process_cache 3rd arg, calls enrich_event per event
- `pnpg/main.py` — imports process_poller_loop, creates process_cache, starts poller_task, cancels poller before worker in shutdown, exposes app.state.process_cache
- `tests/test_capture/test_queue_bridge.py` — 5 original tests updated to new signatures; 6 D-series tests now GREEN
- `tests/test_pipeline/test_worker.py` — 2 direct pipeline_worker() calls updated to pass {} as process_cache

## Decisions Made

1. **Config signature cascade** — config flows as a 4th argument through `make_packet_handler -> _enqueue_packet -> make_packet_event` rather than being captured via a module-level global. This preserves testability and avoids hidden state coupling.

2. **Poller cancelled before worker** — shutdown cancels `poller_task` first, then `worker_task`. This ensures the worker can still read the process cache during any remaining queue drain phase. The plan explicitly documented this ordering requirement.

3. **Empty dict in worker tests** — `pipeline_worker(queue, config, {})` uses an empty cache intentionally. `enrich_event` degrades gracefully to `"unknown process" / pid=-1` on cache miss, which is the correct behavior for isolated unit tests of the worker loop.

## Deviations from Plan

None — plan executed exactly as written.

The sniffer.py update (adding `config` to `make_packet_handler` call in `sniffer_supervisor`) was explicitly called out in the plan's Task 1 action section as a required cascade fix.

## Issues Encountered

None.

## Known Stubs

The following Phase 3-5 stub comments remain in `worker.py` (intentional — each future plan removes one):
- `# Phase 3: event = await dns_resolver(event, executor, loop)`
- `# Phase 4: alerts = detection_engine(event, config)`
- `# Phase 5: storage_writer(event)` and `websocket_push(event)`

These stubs are non-functional placeholder comments, not code. They do not affect the correctness of Phase 2 deliverables.

## Next Phase Readiness

Phase 3 (DNS resolution) is ready to start:
- Every pipeline event now carries `src_ip`, `dst_ip`, `dst_port`, `protocol`, `process_name`, `pid`
- The Phase 3 stub location is at the `# Phase 3` comment in `worker.py`
- DNS enrichment will add `dst_domain` to the event dict following the same immutable enrichment pattern as `enrich_event`

## Self-Check: PASSED

Files verified:
- FOUND: pnpg/capture/queue_bridge.py
- FOUND: pnpg/pipeline/worker.py
- FOUND: pnpg/main.py
- FOUND: .planning/phases/02-process-attribution/02-02-SUMMARY.md

Commits verified:
- a4cc5a0 — feat(02-02): update make_packet_event and queue_bridge signatures per D-01/D-02/D-03
- a5c4895 — feat(02-02): wire enrich_event into pipeline worker and start process poller in lifespan

Tests: 39 passed in 0.19s

---
*Phase: 02-process-attribution*
*Completed: 2026-04-04*
