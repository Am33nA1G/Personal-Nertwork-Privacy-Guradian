---
phase: 05-data-store-and-backend-api
plan: 01
subsystem: database
tags: [postgres, asyncpg, ndjson, apscheduler, storage]
requires:
  - phase: 04-detection-engine
    provides: detector alerts and the worker hook point after detect_event()
provides:
  - PostgreSQL schema and query constants for connection, alert, allowlist, and suppression data
  - NDJSON audit-log writer with rotation and concurrency protection
  - Storage writer and background scheduler primitives for later API and worker wiring
affects: [05-data-store-and-backend-api, api, websocket, storage]
tech-stack:
  added: [asyncpg, python-jose[cryptography], passlib[bcrypt], bcrypt, slowapi, python-multipart, APScheduler, httpx]
  patterns: [asyncpg query constants, mock-first storage testing, asyncio.Lock-protected NDJSON writes]
key-files:
  created: [pnpg/db/pool.py, pnpg/db/schema.sql, pnpg/db/queries.py, pnpg/storage/ndjson.py, pnpg/storage/writer.py, pnpg/scheduler.py, tests/test_storage/test_ndjson.py, tests/test_storage/test_writer.py, tests/test_storage/test_purge.py]
  modified: [pnpg/config.py, requirements.txt]
key-decisions:
  - "Kept the PostgreSQL layer mock-first so Phase 5 can advance without requiring a running local database."
  - "Added a UUID fallback in storage_writer so current pipeline events remain persistable before worker event_id wiring lands."
  - "Used immediate synchronous file appends behind asyncio.Lock for NDJSON durability and simple rotation behavior."
patterns-established:
  - "All Phase 5 SQL lives in pnpg/db/queries.py as named constants with asyncpg $N placeholders."
  - "Storage writes always continue to NDJSON even when PostgreSQL is unavailable or a DB write raises (SYS-04)."
  - "Retention purge runs in 10000-row chunks via APScheduler helpers to avoid unbounded deletes."
requirements-completed: [STORE-01, STORE-02, STORE-03, STORE-04, STORE-05, STORE-06, STORE-07, STORE-08, STORE-09, STORE-10, STORE-11, OBS-04]
duration: 8min
completed: 2026-04-05
---

# Phase 5: Data Store and Backend API Summary

**PostgreSQL schema/query foundations, NDJSON audit logging with rotation, and purge/metrics scheduler primitives for the live pipeline**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-05T18:31:00+05:30
- **Completed:** 2026-04-05T18:39:12+05:30
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments

- Added the Phase 5 persistence foundation under `pnpg/db/` with schema DDL, query constants, and resilient asyncpg pool creation.
- Added NDJSON audit logging, the storage writer, and the scheduler helpers for retention purge and OBS-04 metrics.
- Added 13 new storage tests and verified the full repo still passes with the local `.pytest_tmp` workaround.

## Task Commits

No git commits were created during this workspace session.

## Files Created/Modified

- `requirements.txt` - Added the Phase 5 Python dependencies.
- `pnpg/config.py` - Added database, auth, websocket, NDJSON, and retention config keys.
- `pnpg/db/pool.py` - Added resilient asyncpg pool creation.
- `pnpg/db/schema.sql` - Added the five-table PostgreSQL schema and indexes.
- `pnpg/db/queries.py` - Added named SQL constants for inserts, reads, stats, allowlist, suppressions, and purge operations.
- `pnpg/storage/ndjson.py` - Added NDJSON append and rotation support.
- `pnpg/storage/writer.py` - Added DB plus NDJSON dual-write storage behavior.
- `pnpg/scheduler.py` - Added purge and OBS-04 metric scheduling helpers.
- `tests/test_storage/test_ndjson.py` - Added NDJSON writer TDD coverage.
- `tests/test_storage/test_writer.py` - Added storage writer TDD coverage.
- `tests/test_storage/test_purge.py` - Added purge and metrics helper tests.

## Decisions Made

- Mocked asyncpg pool usage in unit tests instead of requiring PostgreSQL for Plan 01, which keeps the validation loop fast and stable on this machine.
- Generated a fallback UUID inside `storage_writer()` when `event_id` is absent because the current worker event shape does not yet guarantee one.
- Kept NDJSON writes immediate and local instead of buffering because the plan requires simple durability and the measured unit-test throughput does not justify executor complexity yet.

## Deviations from Plan

### Auto-fixed Issues

**1. Local pytest basetemp parent creation**
- **Found during:** Task 1 (NDJSON TDD red run)
- **Issue:** pytest could not create nested `--basetemp .pytest_tmp/...` paths until the parent directory existed on this Windows setup.
- **Fix:** Created the repo-local `.pytest_tmp` directory before rerunning the targeted tests.
- **Files modified:** workspace temp directory only
- **Verification:** `python -m pytest tests/test_storage/test_ndjson.py -x -q --basetemp .pytest_tmp/05-01-ndjson`

**2. Event ID fallback for current pipeline compatibility**
- **Found during:** Task 2 (storage_writer implementation)
- **Issue:** the current pipeline event shape does not yet guarantee `event_id`, but the Phase 5 schema and insert query require it.
- **Fix:** `storage_writer()` now generates a UUID when `event_id` is missing.
- **Files modified:** `pnpg/storage/writer.py`
- **Verification:** `python -m pytest tests/test_storage/ -x -q --basetemp .pytest_tmp/05-01-storage`

---

**Total deviations:** 2 auto-fixed
**Impact on plan:** Both fixes were required for reliable local execution and compatibility with the current pipeline. No scope creep.

## Issues Encountered

- The Phase 5 package install initially failed under sandboxed network restrictions and was retried successfully with approved escalation.

## User Setup Required

None for the code changes in this plan. A running PostgreSQL service is still required before live DB writes can succeed outside mocked tests.

## Next Phase Readiness

- Plan 02 can now build JWT auth and REST endpoints directly on top of the schema, query constants, and config keys added here.
- Plan 03 still needs to wire `storage_writer()` and scheduler lifecycle into `main.py` and the pipeline worker.

---
*Phase: 05-data-store-and-backend-api*
*Completed: 2026-04-05*
