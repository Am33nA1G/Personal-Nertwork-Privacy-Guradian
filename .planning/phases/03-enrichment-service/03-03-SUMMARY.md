---
phase: 03-enrichment-service
plan: "03"
subsystem: pipeline
tags: [dns, geoip, threat-intel, fastapi, asyncio, tdd]
dependency_graph:
  requires:
    - 03-01-PLAN.md
    - 03-02-PLAN.md
  provides:
    - pnpg/pipeline/threat_intel.py
    - pnpg/pipeline/worker.py wired with DNS, GeoIP, and threat intel enrichment
    - pnpg/main.py lifespan initialization and teardown for enrichment resources
    - pnpg/prereqs.py get_probe_type()
  affects:
    - tests/test_pipeline/test_threat_intel.py
    - tests/test_pipeline/test_worker.py
tech_stack:
  added: []
  patterns:
    - Module-level frozenset blocklist for local threat-intel membership checks
    - Immutable event enrichment via {**event, ...}
    - FastAPI lifespan-owned enrichment resource setup and teardown
    - Sequential pipeline enrichment stages in a single worker loop
key_files:
  created:
    - pnpg/pipeline/threat_intel.py
    - tests/test_pipeline/test_threat_intel.py
  modified:
    - pnpg/pipeline/worker.py
    - pnpg/main.py
    - pnpg/prereqs.py
    - tests/test_pipeline/test_worker.py
decisions:
  - Threat-intel membership checks stay local and in-memory via frozenset for O(1) lookup across IPs and hostnames
  - pipeline_worker reuses a 16-thread ThreadPoolExecutor for DNS and runs enrich_event -> enrich_dns -> enrich_geo -> check_threat_intel in order
  - FastAPI lifespan owns DNS cache creation, GeoIP reader lifecycle, blocklist load, and SYS-03 probe-type reporting
metrics:
  completed_date: "2026-04-05"
  tasks_completed: 2
  files_created: 2
  files_modified: 4
  verification: "python -m pytest tests/ -x -q -> 70 passed"
---

# Phase 3 Plan 03: Enrichment Service Summary

**One-liner:** Completed the Phase 3 enrichment layer by adding local threat-intel blocklist checks, wiring DNS + GeoIP + threat intel into the pipeline worker, and extending FastAPI lifespan startup/shutdown to manage enrichment resources.

## Objective

Finish the enrichment service by:
- adding `threat_intel.py` with local blocklist loading, immutable event enrichment, and stale-file warnings
- wiring `enrich_dns`, `enrich_geo`, and `check_threat_intel` into `pipeline_worker()`
- initializing and tearing down enrichment resources from `main.py`
- logging the SYS-03 probe fallback via `get_probe_type()`

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Threat intel module and RED/GREEN tests | `45b3e44` | `pnpg/pipeline/threat_intel.py`, `tests/test_pipeline/test_threat_intel.py` |
| 2 | Worker/lifespan/prereqs wiring and worker test updates | `45b3e44` | `pnpg/pipeline/worker.py`, `pnpg/main.py`, `pnpg/prereqs.py`, `tests/test_pipeline/test_worker.py` |

## Verification Results

- `python -m pytest tests/test_pipeline/test_threat_intel.py -x -q` -> 9 passed
- `python -m pytest tests/ -x -q` -> 70 passed

## Deviations from Plan

1. The repo did not contain the referenced `03-01-SUMMARY.md` or `03-02-SUMMARY.md` files, so this summary follows the existing Phase 1/2 summary style instead of extending missing Phase 3 summaries.

2. Once the real DNS stage was wired into `pipeline_worker()`, the worker tests needed valid `dst_ip` / `src_ip` / `src_port` fields in their helper events. The fix was applied in the test fixture data so the production worker behavior stayed intact.

## Decisions Made

1. **Threat-intel storage model** - The blocklist is loaded into a module-level `frozenset[str]`. This keeps lookups constant-time and avoids any network dependency or per-event parsing overhead.

2. **Stage ordering** - The worker processes events in this order: `enrich_event -> enrich_dns -> enrich_geo -> check_threat_intel`. This preserves the intended enrichment flow and makes `dst_hostname` available before threat-intel hostname checks.

3. **Lifespan ownership** - DNS cache creation, GeoIP reader setup/teardown, blocklist loading, and probe-type reporting all live in `main.py` lifespan so startup state is explicit and shared through `app.state`.

## Outcome

- `pnpg/pipeline/threat_intel.py` exists and implements `load_blocklist()`, `check_threat_intel()`, and `check_blocklist_freshness()`
- `pipeline_worker()` now accepts a shared `dns_cache` and runs all three enrichment stages in sequence
- `main.py` initializes DNS cache, opens GeoIP readers, checks GeoIP freshness, loads the threat-intel blocklist, stores `probe_type`, and closes GeoIP readers during shutdown
- `pnpg/prereqs.py` now exposes `get_probe_type()` and logs the SYS-03 fallback notice
- Full test suite is green

## Self-Check

- FOUND: `pnpg/pipeline/threat_intel.py`
- FOUND: `tests/test_pipeline/test_threat_intel.py`
- FOUND: `pnpg/pipeline/worker.py` with `enrich_dns`, `enrich_geo`, `check_threat_intel`, and `max_workers=16`
- FOUND: `pnpg/main.py` with `dns_cache`, `open_readers`, `check_db_freshness`, `load_blocklist`, `close_readers`, and `get_probe_type`
- FOUND: `pnpg/prereqs.py` with `SYS-03` probe logging
- VERIFIED: `45b3e44` - `feat(03): implement enrichment service — DNS resolver, GeoIP enricher, threat intel blocklist`
