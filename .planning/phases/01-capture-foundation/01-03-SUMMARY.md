---
phase: 01-capture-foundation
plan: "03"
subsystem: capture
tags: [scapy, fastapi, asyncio, threading, exponential-backoff, pipeline, queue]

# Dependency graph
requires:
  - phase: 01-capture-foundation/01-01
    provides: config.py, prereqs.py
  - phase: 01-capture-foundation/01-02
    provides: queue_bridge.py, interface.py, start_sniffer in sniffer.py
provides:
  - sniffer_supervisor coroutine with exponential backoff restart (CAP-10)
  - async pipeline_worker consuming asyncio.Queue in FIFO order (PIPE-01/02/03)
  - pnpg/main.py FastAPI app with lifespan wiring full startup sequence
  - Full 23-test suite GREEN across all Phase 1 plans
affects: [02-process-mapping, 03-dns-resolution, 04-detection-engine, 05-api-frontend]

# Tech tracking
tech-stack:
  added: [fastapi lifespan pattern, concurrent.futures.ThreadPoolExecutor, asyncio.create_task]
  patterns:
    - "Supervisor coroutine: while loop with run_in_executor(thread.join) then asyncio.sleep(backoff)"
    - "Pipeline worker: await queue.get() -> process stages -> queue.task_done() in finally"
    - "FastAPI lifespan: asynccontextmanager, startup sequence before yield, cancel tasks after yield"
    - "Module-level import pattern: import make_packet_handler at top of sniffer.py so tests can patch it"

key-files:
  created:
    - pnpg/capture/sniffer.py (sniffer_supervisor added — CAP-10)
    - pnpg/pipeline/__init__.py
    - pnpg/pipeline/worker.py (pipeline_worker — PIPE-01/02/03/TEST-01)
    - pnpg/main.py (FastAPI app with lifespan)
    - tests/test_capture/test_sniffer.py (3 supervisor tests)
    - tests/test_pipeline/__init__.py
    - tests/test_pipeline/test_worker.py (4 pipeline worker tests)
  modified:
    - pnpg/capture/sniffer.py (added sniffer_supervisor, module-level queue_bridge import)

key-decisions:
  - "sniffer_supervisor uses run_in_executor(None, thread.join) not bare thread.join — required to avoid blocking event loop (RESEARCH Pitfall 5)"
  - "make_packet_handler imported at module level in sniffer.py so tests can patch pnpg.capture.sniffer.make_packet_handler"
  - "pipeline_worker calls queue.task_done() in finally block — guarantees queue.join() unblocks even on error"
  - "ThreadPoolExecutor created once per worker instance, not per event — avoids pool creation overhead"
  - "CancelledError re-raised in pipeline_worker after calling task_done() — ensures clean cancellation"

patterns-established:
  - "Pattern: Supervisor restart — check stop_event -> start thread -> await run_in_executor(join) -> check stop_event -> sleep(backoff) -> increment attempt"
  - "Pattern: Pipeline consumer — await queue.get() in try, stages in try/except Exception, queue.task_done() in finally"
  - "Pattern: FastAPI lifespan — load_config -> prereq checks -> create tasks -> yield -> set stop_event -> cancel tasks -> await tasks swallowing CancelledError"

requirements-completed: [CAP-10, PIPE-01, PIPE-02, PIPE-03, TEST-01]

# Metrics
duration: 16min
completed: 2026-04-01
---

# Phase 1 Plan 03: Sniffer Supervisor, Pipeline Worker, and FastAPI Lifespan Summary

**Async sniffer supervisor with exponential backoff restart (1s/2s/4s..60s cap), FIFO pipeline worker with ThreadPoolExecutor stubs for DNS/process-mapping, and FastAPI lifespan wiring the full load_config->check_npcap->check_admin->select_interface->supervisor->worker startup sequence**

## Performance

- **Duration:** 16 min
- **Started:** 2026-04-01T08:51:46Z
- **Completed:** 2026-04-01T09:08:07Z
- **Tasks:** 2 (TDD: 1 RED commit + 1 GREEN commit)
- **Files modified:** 7

## Accomplishments

- Sniffer supervisor restarts dead threads with exponential backoff (1.0 * 2^attempt, capped at 60s), using non-blocking `run_in_executor(None, thread.join)` to avoid stalling the event loop
- Async pipeline worker consumes queue in FIFO order, logs each event at DEBUG in debug_mode, catches all exceptions with `logging.critical` without crashing, calls `queue.task_done()` in `finally` for reliable join semantics
- FastAPI main.py with lifespan context manager completes the execution backbone: full startup/shutdown sequence with state exposed on `app.state` for future route handlers
- Full test suite: 23 tests across all 3 Phase 1 plans pass GREEN

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 test stubs for sniffer supervisor and pipeline worker** - `35884f8` (test)
2. **Task 2: Implement sniffer supervisor, pipeline worker, and main.py lifespan** - `7eafdc1` (feat)

## Files Created/Modified

- `pnpg/capture/sniffer.py` - Added `sniffer_supervisor` async coroutine (CAP-10); added module-level `make_packet_handler` import
- `pnpg/pipeline/__init__.py` - Empty package init
- `pnpg/pipeline/worker.py` - `pipeline_worker` async coroutine (PIPE-01/02/03, TEST-01, CONFIG-03/SYS-01)
- `pnpg/main.py` - FastAPI app with `lifespan` context manager wiring full startup sequence
- `tests/test_capture/test_sniffer.py` - 3 tests: supervisor_restart, supervisor_backoff_delay, supervisor_graceful_stop
- `tests/test_pipeline/__init__.py` - Empty package init
- `tests/test_pipeline/test_worker.py` - 4 tests: consumes_queue, order_preserved, error_no_crash, debug_mode

## Decisions Made

- `run_in_executor(None, thread.join)` chosen over bare `thread.join()` to await sniffer thread exit without blocking the event loop (RESEARCH.md Pitfall 5 directly addresses this)
- `make_packet_handler` moved to module-level import in sniffer.py so tests can patch `pnpg.capture.sniffer.make_packet_handler` — lazy import inside function body is not patchable via standard mock.patch
- `queue.task_done()` placed in `finally` block so `queue.join()` always unblocks, even when a pipeline stage raises an exception
- ThreadPoolExecutor instantiated once per worker call (not per event) to avoid overhead of repeated pool creation; reused across iterations for future blocking stage dispatch

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Moved make_packet_handler import to module level in sniffer.py**
- **Found during:** Task 2 (running tests after implementing sniffer_supervisor)
- **Issue:** `sniffer_supervisor` imported `make_packet_handler` inside the function body (`from pnpg.capture.queue_bridge import make_packet_handler`). Tests mock `pnpg.capture.sniffer.make_packet_handler` but this attribute only exists if imported at module scope. With a lazy inner import, mock.patch raises `AttributeError: module has no attribute make_packet_handler`.
- **Fix:** Added `from pnpg.capture.queue_bridge import make_packet_handler` at module top; removed the inner import from the function body.
- **Files modified:** `pnpg/capture/sniffer.py`
- **Verification:** All 3 sniffer supervisor tests pass GREEN after fix; 23/23 total tests pass.
- **Committed in:** `7eafdc1` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug)
**Impact on plan:** Required for tests to pass. No scope creep.

## Issues Encountered

None beyond the auto-fixed import bug described above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 1 execution backbone is complete: Scapy captures -> queue bridge -> pipeline worker -> FastAPI app
- main.py lifespan sequence is ready; add route handlers (`/connections`, `/alerts`, `/ws/live`) in Phase 5
- Pipeline worker enrichment stubs (process_mapper, dns_resolver, detection_engine) are in place as comments — Phase 2-4 implementations slot directly into these placeholders
- Concern carried forward: Npcap + Windows interface selection behavior needs empirical validation on target machine (Wi-Fi + possible VPN adapter)

---
*Phase: 01-capture-foundation*
*Completed: 2026-04-01*
