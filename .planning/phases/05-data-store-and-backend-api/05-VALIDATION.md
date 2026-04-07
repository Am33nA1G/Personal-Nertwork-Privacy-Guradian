---
phase: 5
slug: data-store-and-backend-api
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-05
updated: 2026-04-05
---

# Phase 5 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 + httpx 0.28.1 |
| **Config file** | `pytest.ini` + `tests/conftest.py` |
| **Quick run command** | Use the task-specific verify command from the map below until all Phase 5 test packages exist. |
| **Full suite command** | `python -m pytest tests/ -x -q --basetemp .pytest_tmp/full` |
| **Estimated runtime** | ~30-45 seconds |
| **DB requirement** | Unit tests must mock `asyncpg` pool. Integration-style tests may use `PNPG_TEST_DB_DSN` when a local PostgreSQL test DB is available. |
| **Local temp workaround** | Use `--basetemp .pytest_tmp/...` on this machine to avoid `WinError 5` failures under `%TEMP%`. |

---

## Sampling Rate

- After every task commit: Run the task-specific verify command from the map below
- After every plan wave: Run `python -m pytest tests/ -x -q --basetemp .pytest_tmp/full`
- Before `/gsd:verify-work`: Full suite must be green
- Max feedback latency: 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 1 | STORE-05, STORE-06, STORE-07 | unit | `python -m pytest tests/test_storage/test_ndjson.py -x -q --basetemp .pytest_tmp/05-01-ndjson` | Yes | green |
| 5-01-02 | 01 | 1 | STORE-01, STORE-02, STORE-03, STORE-08, STORE-09, SYS-04 | unit | `python -m pytest tests/test_storage/test_writer.py -x -q --basetemp .pytest_tmp/05-01-writer` | Yes | green |
| 5-01-03 | 01 | 1 | STORE-11, OBS-04 | unit | `python -m pytest tests/test_storage/test_purge.py -x -q --basetemp .pytest_tmp/05-01-purge` | Yes | green |
| 5-02-01 | 02 | 2 | AUTH-01, AUTH-02, AUTH-03, AUTH-04 | unit/integration | `python -m pytest tests/test_api/test_auth.py -x -q --basetemp .pytest_tmp/05-02-auth` | Yes | green |
| 5-02-02 | 02 | 2 | API-01, API-02, API-03, API-04, API-13 | unit/integration | `python -m pytest tests/test_api/test_connections.py tests/test_api/test_alerts.py tests/test_api/test_stats.py -x -q --basetemp .pytest_tmp/05-02-core` | Yes | green |
| 5-02-03 | 02 | 2 | API-05, API-11, API-12, ALLOW-05, ALLOW-06, SUPP-03, SUPP-04, SUPP-05 | unit/integration | `python -m pytest tests/test_api/test_allowlist.py tests/test_api/test_alerts.py tests/test_api/test_health.py -x -q --basetemp .pytest_tmp/05-02-support` | Yes | green |
| 5-03-01 | 03 | 3 | API-06, API-07, API-08, API-09, API-10, AUTH-03 | unit/integration | `python -m pytest tests/test_ws tests/test_api/test_websocket.py -x -q --basetemp .pytest_tmp/05-03-ws` | Yes | green |
| 5-03-02 | 03 | 3 | SYS-02, SYS-04 | unit/integration | `python -m pytest tests/test_api/test_shutdown.py -x -q --basetemp .pytest_tmp/05-03-shutdown` | Yes | green |
| 5-03-03 | 03 | 3 | TEST-02 | smoke | `python tools/load_generator.py --rate 100 --duration 5 --base-url http://localhost:8000 --token <jwt>` | Yes | pending |

Status legend: `pending`, `green`, `red`, `flaky`

---

## Wave 0 Requirements

- [x] `tests/test_storage/` directory created
- [x] `tests/test_storage/__init__.py` created
- [x] `tests/test_storage/test_ndjson.py` - stubs for STORE-05, STORE-06, STORE-07
- [x] `tests/test_storage/test_writer.py` - stubs for STORE-01, STORE-02, STORE-03, STORE-08, STORE-09, SYS-04
- [x] `tests/test_storage/test_purge.py` - stubs for STORE-11 and OBS-04 scheduler behavior
- [x] `tests/test_api/` directory created
- [x] `tests/test_api/__init__.py` created
- [x] `tests/test_api/conftest.py` - async client, mock pool, auth headers, ws manager fixtures
- [x] `tests/test_api/test_auth.py` - stubs for AUTH-01..04
- [x] `tests/test_api/test_connections.py` - stubs for API-01
- [x] `tests/test_api/test_alerts.py` - stubs for API-02, SUPP-03, SUPP-04, SUPP-05
- [x] `tests/test_api/test_allowlist.py` - stubs for ALLOW-05..06
- [x] `tests/test_api/test_stats.py` - stubs for API-03..04
- [x] `tests/test_api/test_health.py` - stubs for API-05, API-12
- [x] `tests/test_api/test_websocket.py` - stubs for AUTH-03 and API-06..10 endpoint behavior
- [x] `tests/test_api/test_shutdown.py` - stubs for SYS-02 and SYS-04 recovery/flush behavior
- [x] `tests/test_ws/` directory created
- [x] `tests/test_ws/__init__.py` created
- [x] `tests/test_ws/test_manager.py` - WsManager unit tests
- [x] `tools/load_generator.py` scaffolded for TEST-02 smoke verification
- [ ] PostgreSQL test database strategy documented: mock-by-default, `PNPG_TEST_DB_DSN` optional for real DB integration runs
- [x] Required packages added to `requirements.txt`: `asyncpg`, `python-jose[cryptography]`, `passlib[bcrypt]`, `bcrypt`, `slowapi`, `python-multipart`, `APScheduler`, `httpx`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PostgreSQL service startup and schema application | STORE-01, STORE-10 | Requires local service management and real database | Start PostgreSQL, create `pnpg_test`, apply `schema.sql`, then confirm tables and indexes exist with `psql` or `\d`. |
| WebSocket 500ms batching under live traffic | API-06 | Requires live event flow and wall-clock inspection | Start server, open `/api/v1/ws/live`, generate traffic, confirm pushes arrive in batches around 500ms rather than per-packet. |
| Graceful shutdown flush | SYS-02 | Requires process signal and buffered writes | Start server, enqueue events, send shutdown signal, confirm NDJSON files and DB contain buffered records before exit. |

---

## Validation Sign-Off

- [x] All tasks have automated verify or explicit Wave 0 dependency coverage
- [x] Sampling continuity: no three consecutive tasks without automated verification
- [x] Wave 0 covers all currently missing Phase 5 references
- [x] No watch-mode flags
- [x] Feedback latency target is under 30 seconds
- [x] `nyquist_compliant: true` is set in frontmatter

**Approval:** approved for execution on 2026-04-05; Wave 0 stubs are created incrementally by the Phase 5 plans
