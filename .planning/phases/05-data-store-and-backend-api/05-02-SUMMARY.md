---
phase: 05-data-store-and-backend-api
plan: 02
subsystem: api
tags: [fastapi, jwt, bcrypt, slowapi, rest]
requires:
  - phase: 05-data-store-and-backend-api
    provides: PostgreSQL query layer, storage config, and scheduler/db primitives from 05-01
provides:
  - JWT auth and first-run password setup endpoints
  - Versioned REST routes for connections, alerts, allowlist, stats, status, and health
  - main.py lifespan wiring for DB pool, auth state, NDJSON writer, scheduler, and API routers
affects: [05-data-store-and-backend-api, frontend, websocket, auth]
tech-stack:
  added: [fastapi routers, python-jose, slowapi, passlib, bcrypt]
  patterns: [single-user bearer auth, consistent API envelopes, mock-first async route testing]
key-files:
  created: [pnpg/api/auth.py, pnpg/api/models.py, pnpg/api/deps.py, pnpg/api/middleware.py, pnpg/api/routes/connections.py, pnpg/api/routes/alerts.py, pnpg/api/routes/allowlist.py, pnpg/api/routes/stats.py, pnpg/api/routes/status.py, tests/test_api/test_auth.py, tests/test_api/test_connections.py, tests/test_api/test_alerts.py, tests/test_api/test_allowlist.py, tests/test_api/test_stats.py, tests/test_api/test_health.py]
  modified: [pnpg/main.py, tests/test_api/conftest.py]
key-decisions:
  - "Kept API tests fully ASGI-local with mocked pool/state instead of depending on main.py lifespan or a live PostgreSQL service."
  - "Added a direct bcrypt fallback while retaining pwd_context because passlib and bcrypt 5 are incompatible on this machine."
  - "Used SlowAPI's configured default string limit in decorators because its callable API cannot access the request object as the plan sketch assumed."
patterns-established:
  - "All protected REST routes use Depends(get_current_user); /health remains public."
  - "List endpoints return {data, pagination}; single-object endpoints return {data}."
  - "Allowlist and suppression writes update DetectorState in memory immediately after DB success."
requirements-completed: [AUTH-01, AUTH-02, AUTH-03, AUTH-04, API-01, API-02, API-03, API-04, API-05, API-09, API-11, API-12, API-13, ALLOW-05, ALLOW-06, SUPP-03, SUPP-04, SUPP-05]
duration: 10min
completed: 2026-04-05
---

# Phase 5: Data Store and Backend API Summary

**JWT auth, first-run setup, and the full `/api/v1` REST surface for stored connections, alerts, stats, allowlist, and health/status**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-05T18:39:30+05:30
- **Completed:** 2026-04-05T18:49:58+05:30
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments

- Added JWT auth with setup and login flows, shared FastAPI dependencies, envelope models, and SlowAPI middleware.
- Added the REST route layer for connections, alerts, suppressions, allowlist, stats, status, and health with mock-first tests.
- Extended `main.py` lifespan to initialize DB/auth/scheduler state and mounted all `/api/v1` routers without breaking the existing root `/status` endpoint.

## Task Commits

No git commits were created during this workspace session.

## Files Created/Modified

- `pnpg/api/auth.py` - JWT setup/login, secret resolution, auth dependency, bcrypt fallback helpers
- `pnpg/api/models.py` - API envelope and request models
- `pnpg/api/deps.py` - shared request-state dependencies
- `pnpg/api/middleware.py` - SlowAPI setup
- `pnpg/api/routes/connections.py` - paginated connections endpoint
- `pnpg/api/routes/alerts.py` - alerts list, patch, and suppressions endpoints
- `pnpg/api/routes/allowlist.py` - allowlist CRUD with detector sync
- `pnpg/api/routes/stats.py` - summary and timeseries endpoints
- `pnpg/api/routes/status.py` - authenticated status and public health endpoints
- `pnpg/main.py` - lifespan/router wiring for auth, pool, writer, scheduler, and route includes
- `tests/test_api/conftest.py` - API app/client fixtures
- `tests/test_api/test_auth.py` - auth/setup coverage
- `tests/test_api/test_connections.py` - connections and rate-limit coverage
- `tests/test_api/test_alerts.py` - alerts and suppress coverage
- `tests/test_api/test_allowlist.py` - allowlist CRUD coverage
- `tests/test_api/test_stats.py` - stats endpoint coverage
- `tests/test_api/test_health.py` - public health and protected status coverage

## Decisions Made

- Used a separate ASGI test app fixture instead of `pnpg.main` in tests so Phase 5 API behavior can be validated without Npcap/admin prerequisites.
- Preserved `pwd_context` in the auth module for plan compliance, but routed hashing/verification through a direct `bcrypt` fallback path for runtime compatibility.
- Applied SlowAPI using the configured default limit string in decorators and validated the real `100/minute` threshold in tests rather than relying on a non-working dynamic callback.

## Deviations from Plan

### Auto-fixed Issues

**1. passlib and bcrypt 5 compatibility**
- **Found during:** Task 1 (auth implementation)
- **Issue:** `pwd_context.hash()` failed at runtime because `passlib` and `bcrypt 5.0.0` are incompatible in this environment.
- **Fix:** Added `hash_password()` and `verify_password()` helpers that try `pwd_context` first and fall back to direct `bcrypt`.
- **Files modified:** `pnpg/api/auth.py`, `tests/test_api/conftest.py`
- **Verification:** `python -m pytest tests/test_api/test_auth.py -x -q --basetemp .pytest_tmp/05-02-auth`

**2. SlowAPI callable limit provider mismatch**
- **Found during:** Task 2 (route implementation)
- **Issue:** SlowAPI's callable limit provider does not receive the request object, so the dynamic `api_rate_limit` callback from the plan sketch raised `TypeError`.
- **Fix:** Switched route decorators to the configured default limit string and validated the threshold with 101 requests in the test suite.
- **Files modified:** `pnpg/api/routes/connections.py`, `pnpg/api/routes/alerts.py`, `pnpg/api/routes/allowlist.py`, `pnpg/api/routes/stats.py`, `tests/test_api/test_connections.py`
- **Verification:** `python -m pytest tests/test_api/ -x -q --basetemp .pytest_tmp/05-02-api`

---

**Total deviations:** 2 auto-fixed
**Impact on plan:** Both fixes were necessary for a working implementation in this environment. Scope remained within Plan 02.

## Issues Encountered

- None beyond the two auto-fixed library/runtime mismatches above.

## User Setup Required

None for the code path itself. A real PostgreSQL service is still optional for mocked tests but required before live API data reads are expected to succeed outside test mode.

## Next Phase Readiness

- Plan 03 can now add the WebSocket manager and wire live storage/websocket pushes into the pipeline using the auth and REST foundation completed here.
- The API surface Phase 6 will consume already exists, so the remaining Phase 5 backend gap is live event delivery and shutdown behavior.

---
*Phase: 05-data-store-and-backend-api*
*Completed: 2026-04-05*
