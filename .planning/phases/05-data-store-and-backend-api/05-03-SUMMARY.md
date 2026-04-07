---
phase: 05-data-store-and-backend-api
plan: 03
subsystem: api
tags: [websocket, asyncio, fastapi, shutdown, load-testing]
requires:
  - phase: 05-data-store-and-backend-api
    provides: storage writer, DB/runtime config, auth routes, and REST API foundation from 05-01 and 05-02
provides:
  - WebSocket live stream manager and authenticated /api/v1/ws/live endpoint
  - Pipeline worker wiring for storage and live broadcast after detection
  - Shared shutdown helper and load generator scaffold for TEST-02
affects: [05-data-store-and-backend-api, websocket, pipeline, frontend, performance]
tech-stack:
  added: [FastAPI websocket route, asyncio websocket manager, httpx load generator]
  patterns: [batched websocket fanout, shared shutdown helper, worker post-detection storage+broadcast hook]
key-files:
  created: [pnpg/ws/manager.py, pnpg/api/routes/ws.py, tools/load_generator.py, tests/test_ws/test_manager.py, tests/test_api/test_websocket.py, tests/test_api/test_shutdown.py]
  modified: [pnpg/pipeline/worker.py, pnpg/main.py]
key-decisions:
  - "Added _flush_once() and _heartbeat_once() helpers inside WsManager so batching and heartbeat logic can be tested deterministically without timing-heavy infinite-loop tests."
  - "Used a shared shutdown_runtime() helper in main.py so the lifespan cleanup order is testable and matches the Phase 5 shutdown contract."
  - "Kept the load generator as an authenticated request-rate tool against the REST API; the live smoke run remains separate from unit/regression verification."
patterns-established:
  - "Worker writes to storage and websocket fanout only after detect_event() completes."
  - "WebSocket clients are tracked with per-client deques and are dropped on send failure without crashing the broadcast loop."
  - "Runtime shutdown now centralizes stop_event, task cancellation, websocket stop, scheduler stop, NDJSON flush, DB close, and GeoIP close."
requirements-completed: [API-06, API-07, API-08, API-09, API-10, SYS-02, SYS-04, TEST-02]
duration: 8min
completed: 2026-04-05
---

# Phase 5: Data Store and Backend API Summary

**Live websocket fanout, pipeline storage/broadcast wiring, shared shutdown cleanup, and the TEST-02 load generator scaffold**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-05T18:50:30+05:30
- **Completed:** 2026-04-05T18:58:40+05:30
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Added `WsManager`, the authenticated `/api/v1/ws/live` route, client filters, batching, heartbeat, and disconnect resilience.
- Wired the pipeline worker to call `storage_writer()` and `ws_manager.broadcast()` after detection, and moved runtime cleanup into a reusable shutdown helper.
- Added the TEST-02 load generator scaffold and kept the full suite green after the final Phase 5 wiring changes.

## Task Commits

No git commits were created during this workspace session.

## Files Created/Modified

- `pnpg/ws/manager.py` - batched websocket manager with heartbeat and client filtering
- `pnpg/api/routes/ws.py` - JWT-authenticated websocket endpoint
- `pnpg/pipeline/worker.py` - storage and live-broadcast hooks after detection
- `pnpg/main.py` - websocket manager startup, router include, and shared shutdown cleanup
- `tools/load_generator.py` - authenticated request-rate load generator
- `tests/test_ws/test_manager.py` - websocket manager unit tests
- `tests/test_api/test_websocket.py` - websocket endpoint auth tests
- `tests/test_api/test_shutdown.py` - shutdown helper tests

## Decisions Made

- Added one-shot websocket helpers inside `WsManager` to keep the tests deterministic instead of relying on sleeping against infinite loops.
- Factored cleanup into `shutdown_runtime()` because the shutdown sequence is now complex enough to warrant a single shared code path.
- Kept TEST-02 verification to `--help` plus file readiness in this plan; the actual live load run remains a UAT/manual step because it needs a running backend and JWT token.

## Deviations from Plan

### Auto-fixed Issues

**1. Deterministic websocket test helpers**
- **Found during:** Task 1 (WsManager tests)
- **Issue:** Direct tests against `_flush_loop()` were timing-fragile and could hang around task cancellation.
- **Fix:** Added `_flush_once()` and `_heartbeat_once()` helpers and used them in unit tests while keeping `_flush_loop()` and `_heartbeat_loop()` for runtime use.
- **Files modified:** `pnpg/ws/manager.py`, `tests/test_ws/test_manager.py`
- **Verification:** `python -m pytest tests/test_ws/ tests/test_api/test_websocket.py -x -q --basetemp .pytest_tmp/05-03-ws`

**2. Shared shutdown helper for testability**
- **Found during:** Task 2 (shutdown coverage)
- **Issue:** The existing lifespan shutdown logic was embedded inline and not directly testable.
- **Fix:** Added `shutdown_runtime()` and routed lifespan cleanup through it.
- **Files modified:** `pnpg/main.py`, `tests/test_api/test_shutdown.py`
- **Verification:** `python -m pytest tests/test_api/test_shutdown.py -x -q --basetemp .pytest_tmp/05-03-shutdown`

---

**Total deviations:** 2 auto-fixed
**Impact on plan:** Both changes improved correctness and testability without changing scope.

## Issues Encountered

- None beyond the two auto-fixed testability/runtime-shape adjustments above.

## User Setup Required

The load generator needs a running backend and a valid JWT token before the live TEST-02 smoke command can be executed.

## Next Phase Readiness

- All three Phase 5 implementation plans are complete and the backend is ready for Phase 5 UAT.
- Phase 6 frontend work now has the REST API and websocket surfaces it needs.

---
*Phase: 05-data-store-and-backend-api*
*Completed: 2026-04-05*
