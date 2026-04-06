---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 06-01-PLAN.md — scaffold, auth, WebSocket, live table
last_updated: "2026-04-06T01:48:12.590Z"
last_activity: 2026-04-06
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 16
  completed_plans: 10
  percent: 71
---

# Project State

## Project Reference

See: [.planning/PROJECT.md](C:/Users/alame/Desktop/network%20Lab%20project/.planning/PROJECT.md)

**Core value:** Users can see exactly which apps are talking to the internet and get alerted when something looks suspicious without needing to understand Wireshark.
**Current focus:** Phase 06 — frontend-dashboard

## Current Position

Phase: 06 (frontend-dashboard) — EXECUTING
Plan: 2 of 3
Status: Ready to execute
Last activity: 2026-04-06

Progress: [#######---] 71%

## Completed Work

- Phase 1 complete: capture foundation, prerequisite gates, queue bridge, sniffer supervisor, FastAPI lifespan
- Phase 2 complete: process attribution cache, poller loop, worker integration
- Phase 3 complete: DNS resolver, GeoIP enrichment, threat intel blocklist, worker wiring
- Phase 4 complete: detector state, DET-01 through DET-07, allowlist, suppression, rate limiting, pipeline integration
- Phase 5 complete: PostgreSQL storage, NDJSON logs, JWT auth, REST API, WebSocket stream, graceful shutdown, and UAT verification
- Phase 6 Plan 01 complete: Next.js 14 scaffold, Bootstrap 5 dark theme, JWT auth flow, useWebSocket with exponential backoff, ConnectionsTable with DOM-mutation delta injection

## Key Decisions

- Scapy sniffing remains on a dedicated daemon thread; the async queue bridge is the stable boundary between capture and the FastAPI event loop.
- Process attribution uses a proactive 200ms `psutil.net_connections()` polling cache and never performs per-packet process lookups.
- DNS reverse lookups stay in a thread pool with timeout and cache; GeoIP and threat intel remain local-only enrichments.
- Detector state is initialized in lifespan and shared with the worker so allowlist, suppression, rate limiting, and first-seen destination tracking remain in memory across events.
- Phase 5 will extend the existing worker after `detect_event()` with storage and WebSocket broadcast hooks rather than restructuring the pipeline.
- Phase 5 validation must use workspace-local `--basetemp .pytest_tmp/...` on this machine to avoid `%TEMP%` access-denied failures from `tmp_path`.
- Auth hashing uses a direct bcrypt fallback behind `pnpg.api.auth` because `passlib` is incompatible with `bcrypt 5` in this environment.
- SlowAPI is active for the REST layer, but its decorators use the configured default limit string rather than a request-aware callback due library API constraints.
- Live websocket delivery uses `WsManager` with per-client deques, batch flush, heartbeat, and disconnect-on-send-failure behavior.
- Runtime shutdown is centralized in `pnpg.main.shutdown_runtime()` so websocket stop, NDJSON flush, DB close, and GeoIP close happen in a single tested path.
- PostgreSQL is running locally on port `5433`, so `config.yaml` overrides the default DSN to `postgresql://pnpg:pnpg@localhost:5433/pnpg`.
- Live DB inserts required storage-layer coercion of timestamp strings, UUID strings, and text-like protocol fields before asyncpg writes.
- next.config.mjs retained as ESM format (not converted to .js CJS); API proxy rewrites work identically.
- Jest 30 requires `next/jest.js` import (with .js extension) for ESM compatibility; bare `next/jest` throws ERR_MODULE_NOT_FOUND.
- ConnectionsTable uses prop-driven useEffect injection pattern (newEvents prop) rather than an imperative handle for simpler parent wiring.

## Pending Todos

- Phase 6 planning artifacts created:
  - 06-RESEARCH.md (existing, HIGH confidence, preserved)
  - 06-VALIDATION.md (new — backend contract locks, stack locks, architecture decisions, anti-pattern checklist)
  - 06-01-PLAN.md (new — scaffold, auth flow, WebSocket hook, live connections table)
  - 06-02-PLAN.md (new — alerts panel, suppress/resolve, pause/resume, error/loading states)
  - 06-03-PLAN.md (new — charts, allowlist manager, capture status, integration polish, final verification)
  - 06-UAT.md (new — 14 UAT tests covering all 8 roadmap success criteria)
- ROADMAP.md progress table corrected (Phase 5 was wrongly showing 0/3; now shows 3/3 Complete)
- Phase 6 Plan 01 COMPLETE — resume at 06-02-PLAN.md (alerts panel, suppress/resolve, error/loading states)

## Blockers and Concerns

- Rate limiting (API-11: 100 req/min) will throttle UAT iteration against live backend — plan 60s waits between heavy test runs or use a dedicated low-rate test scenario
- CORS for WebSocket from Next.js dev server (`localhost:3000`) to backend (`:8001`) is assumed permissive for localhost; validate during 06-01 scaffold smoke test
- Phase 7 still needs a dedicated perf-exempt endpoint for the 10,000 events/sec load test (carry-forward from Phase 5 UAT gap)

## Session Continuity

Last session: 2026-04-06T01:48:12.581Z
Stopped at: Completed 06-01-PLAN.md — scaffold, auth, WebSocket, live table
Resume file: None
