---
status: complete
phase: 05-data-store-and-backend-api
source: [roadmap success criteria, 05-01/05-02/05-03 acceptance criteria]
started: 2026-04-05
updated: 2026-04-05
---

## Current Test

number: 10
name: Full suite still green - no regressions
expected: |
  Run: python -m pytest tests/ -x -q --basetemp .pytest_tmp/full
  Output should show the full repository test suite passing with no failures.
awaiting: complete

## Tests

### 1. Cold Start - Phase 5 imports and lifespan resources
expected: Run: `python -c "from pnpg.db.pool import create_pool; from pnpg.storage.ndjson import NdjsonWriter; from pnpg.api.auth import router as auth_router; from pnpg.ws.manager import WsManager; print('phase5 imports ok')"` - output shows `phase5 imports ok` with no import errors.
result: [passed] `phase5 imports ok`

### 2. Connections API - paginated enriched connection history
expected: Run: `python -m pytest tests/test_api/test_connections.py -x -q --basetemp .pytest_tmp/05-uat-connections` - `/api/v1/connections` returns paginated connection objects including hostname, country, ASN, and threat intel fields.
result: [passed] `4 passed in 2.55s`; live `/api/v1/connections?page_size=3` also returned stored rows on port 8001.

### 3. Auth - login returns JWT and protected routes reject missing token
expected: Run: `python -m pytest tests/test_api/test_auth.py -x -q --basetemp .pytest_tmp/05-uat-auth` - valid login returns access token and refresh token; protected routes return 401 without valid JWT.
result: [passed] `6 passed in 2.54s`; live login against port 8001 returned a JWT successfully.

### 4. Alerts API - active alerts list and suppress action
expected: Run: `python -m pytest tests/test_api/test_alerts.py -x -q --basetemp .pytest_tmp/05-uat-alerts` - `/api/v1/alerts` returns active alerts; PATCH suppress updates alert status to `suppressed`.
result: [passed] `3 passed in 1.84s`; live `/api/v1/alerts?page_size=5` returned active alerts.

### 5. Stats API - 24h summary aggregates
expected: Run: `python -m pytest tests/test_api/test_stats.py -x -q --basetemp .pytest_tmp/05-uat-stats` - `/api/v1/stats/summary` returns total connections, unique destinations, active alerts, and top process metrics.
result: [passed] `2 passed in 1.34s`

### 6. Allowlist API - GET, POST, DELETE with detector sync
expected: Run: `python -m pytest tests/test_api/test_allowlist.py -x -q --basetemp .pytest_tmp/05-uat-allowlist` - `/api/v1/allowlist` lists rules, POST creates, DELETE removes, and detector allowlist stays in sync.
result: [passed] `4 passed in 2.34s`

### 7. WebSocket - 500ms batches and heartbeat
expected: Run: `python -m pytest tests/test_ws tests/test_api/test_websocket.py -x -q --basetemp .pytest_tmp/05-uat-ws` - `/api/v1/ws/live` batches updates around 500ms, emits heartbeat, supports filters, and drops slow clients cleanly.
result: [passed] `11 passed in 0.22s`

### 8. Graceful Shutdown - buffered writes flushed before exit
expected: Run: `python -m pytest tests/test_api/test_shutdown.py -x -q --basetemp .pytest_tmp/05-uat-shutdown` - shutdown flushes NDJSON, closes DB pool, and stops stream resources without data loss.
result: [passed] `3 passed in 0.52s`

### 9. OBS-04 and retention jobs - scheduler behavior
expected: Run: `python -m pytest tests/test_storage/test_purge.py -x -q --basetemp .pytest_tmp/05-uat-scheduler` - scheduler purge job applies retention windows and OBS-04 metrics logging runs every 5 seconds.
result: [passed] `3 passed in 0.12s`

### 10. Full suite still green - no regressions
expected: Run: `python -m pytest tests/ -x -q --basetemp .pytest_tmp/full` - all repo tests pass with 0 failures and 0 errors.
result: [passed] `158 passed in 11.24s`

## Summary

total: 10
passed: 10
issues: 1
blocked: 0
skipped: 0
pending: 0

## Gaps

- Live TEST-02 smoke against `http://127.0.0.1:8001` executed successfully (`100 successful, 138 errors in 5s`), but the target `/api/v1/connections` route is protected by API-11 rate limiting (`100/minute`). Phase 7 performance testing should use a dedicated non-rate-limited path or an explicit perf exemption rather than treating that result as throughput capacity.
