---
phase: 06-frontend-dashboard
doc: validation
status: ready
created: 2026-04-06
source: [06-RESEARCH.md, ROADMAP.md, REQUIREMENTS.md, Phase 5 backend source]
---

# Phase 6 Validation: Frontend Dashboard

**Purpose:** Confirm all preconditions are met before a single line of frontend code is written.
Every row in every table below must be GREEN before execution begins.

---

## 1. Backend Contract Locks

The following contracts are extracted directly from Phase 5 source code and are locked.
Frontend implementation MUST NOT invent endpoints, change URL paths, or assume different shapes.

### 1.1 Authentication

| Contract | Value | Source | Status |
|----------|-------|--------|--------|
| Login endpoint | `POST /api/v1/auth/login` | `pnpg/api/auth.py:120` | LOCKED |
| Login body | `{ "password": "<string>" }` | `pnpg/api/models.py` LoginRequest | LOCKED |
| Login response | `{ "data": { "access_token", "refresh_token", "token_type": "bearer" } }` | `pnpg/api/auth.py:152-158` | LOCKED |
| First-run setup | `POST /api/v1/auth/setup` — required before login works | `pnpg/api/auth.py:103-117` | LOCKED |
| JWT algorithm | HS256 | `pnpg/api/auth.py:133` | LOCKED |
| JWT expiry | 8 hours | `config["jwt_expiry_hours"]` | LOCKED |
| JWT subject | `"pnpg-user"` | `pnpg/api/auth.py:135` | LOCKED |
| WS auth mechanism | Query param `?token=<jwt>` | `pnpg/api/routes/ws.py:14` | LOCKED |
| WS auth failure code | WebSocket close code `4001` | `pnpg/api/routes/ws.py:20` | LOCKED |

### 1.2 WebSocket Live Stream

| Contract | Value | Source | Status |
|----------|-------|--------|--------|
| WS endpoint URL | `ws://127.0.0.1:8001/api/v1/ws/live?token=<jwt>` | `pnpg/api/routes/ws.py:13` | LOCKED |
| Batch frame type | `{ "type": "batch", "events": [...] }` | `pnpg/ws/manager.py` broadcast format | LOCKED |
| Heartbeat frame type | `{ "type": "heartbeat", "ts": <float> }` | `pnpg/ws/manager.py` heartbeat format | LOCKED |
| Batch interval | 500 ms | `config["ws_batch_interval_ms"]` | LOCKED |
| Heartbeat interval | 10 s | `config["ws_heartbeat_interval_s"]` | LOCKED |
| Max events per batch | 100 | `config["ws_max_batch_size"]` | LOCKED |
| Events payload shape | Each event in `events` array has `connections: [...]` and `alerts: [...]` arrays | `pnpg/pipeline/worker.py` broadcast call | LOCKED |
| Client filter message | `{ "type": "filter", "data": { "process": "..." } }` | `pnpg/api/routes/ws.py:32-33` | LOCKED |

### 1.3 REST Endpoints

| Endpoint | Method | Auth | Response Envelope | Source | Status |
|----------|--------|------|-------------------|--------|--------|
| `/api/v1/connections` | GET | Bearer | `{ data: [...], pagination: { page, page_size, total } }` | `routes/connections.py:47-50` | LOCKED |
| `/api/v1/alerts` | GET | Bearer | `{ data: [...], pagination: { ... } }` | `routes/alerts.py:60-63` | LOCKED |
| `/api/v1/alerts/:alert_id` | PATCH | Bearer | `{ data: <updatedAlert> }` | `routes/alerts.py:102` | LOCKED |
| `/api/v1/suppressions` | GET | Bearer | `{ data: [...] }` | `routes/alerts.py:117-118` | LOCKED |
| `/api/v1/suppressions/:id` | DELETE | Bearer | `{ data: { deleted: true } }` | `routes/alerts.py:147` | LOCKED |
| `/api/v1/allowlist` | GET | Bearer | `{ data: [...] }` | `routes/allowlist.py:31` | LOCKED |
| `/api/v1/allowlist` | POST | Bearer | `{ data: <createdRule> }` | `routes/allowlist.py:67` | LOCKED |
| `/api/v1/allowlist/:rule_id` | DELETE | Bearer | `{ data: { deleted: true } }` | `routes/allowlist.py:93` | LOCKED |
| `/api/v1/stats/summary` | GET | Bearer | `{ data: { total_connections, unique_destinations, active_alerts, top_processes, top_destinations } }` | `routes/stats.py:31-37` | LOCKED |
| `/api/v1/stats/timeseries` | GET | Bearer | `{ data: [{ bucket, count }] }` | `routes/stats.py:61-63` | LOCKED |
| `/api/v1/status` | GET | Bearer | `{ data: { capture, interface, uptime, probe_type } }` | `routes/status.py:21-29` | LOCKED |
| `/api/v1/health` | GET | None | `{ data: { status, probe, db, stream } }` | `routes/status.py:44-50` | LOCKED |

### 1.4 PATCH /api/v1/alerts/:id Action Values

```
body: { "action": "suppress" | "resolve", "reason": "<optional string>" }
```
Source: `pnpg/api/models.py` `AlertAction` model + `routes/alerts.py:80`

### 1.5 POST /api/v1/allowlist Body

```
{ "process_name"?: string, "dst_ip"?: string, "dst_hostname"?: string,
  "expires_at"?: ISO8601, "reason"?: string }
```
Source: `pnpg/api/models.py` `AllowlistRuleCreate` + `routes/allowlist.py:36`

---

## 2. Technology Stack Locks

All versions are pinned from research (verified via npm registry on 2026-04-05).
No substitutions are permitted.

| Package | Pinned Version | Reason |
|---------|----------------|--------|
| next | 14.2.35 | Mandated by project constraints; 14.x maintenance line |
| react | 18.3.1 | Next.js 14 peer `^18.2.0`; 18.3.1 is latest in series |
| react-dom | 18.3.1 | Paired with react |
| recharts | 2.15.4 | Mandated; 2.15.4 is latest stable 2.x |
| bootstrap | 5.3.8 | Mandated; npm only — no CDN |
| typescript | bundled by Next.js | Do not add separately |
| @types/react | 18.x | Type safety |
| @types/react-dom | 18.x | Type safety |
| @types/node | 20.x | Next.js config types |

**Router decision: Pages Router** (`--no-app` flag)
- Rationale: Single-screen WebSocket dashboard. App Router adds RSC complexity with zero benefit.
  All content is live-updated via client-side WebSocket state. No server components needed.
- Consequence: Use `pages/` directory structure, NOT `app/`. If `app/` directory appears after scaffold, delete it.

**No additional packages permitted without explicit justification:**
- No Redux, Zustand, or other state management
- No socket.io or reconnecting-websocket
- No Axios (use `fetch`)
- No Tailwind (Bootstrap 5 is the styling system)
- No animation libraries

---

## 3. Architecture Decisions (Locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Token storage | `sessionStorage` | 8h JWT; persists on refresh within tab; expires on tab close; appropriate for local single-user tool |
| Table live updates | DOM mutation via `useRef<HTMLTableSectionElement>` + `prepend` | Prevents full table re-render on every 500ms push (UI-06) |
| Table column set | Time, App, Domain, Country (flag emoji), ASN, IP, Port, Protocol | Resolves three-way conflict: ROADMAP goal says "country+ASN"; ROADMAP success criterion says "Flag"; research says "Flag". Decision: flag in Country column + ASN as its own column. "Severity" is NOT a table column — it belongs in AlertsPanel |
| WS instance storage | `useRef<WebSocket>` (not state) | Prevents infinite reconnect loops; state changes trigger re-render |
| Chart update rate | Recharts state updated at 1Hz via `setInterval`, WS buffer updated immediately | Prevents Recharts re-rendering every 500ms |
| CPS chart data source | WebSocket stream (client-side buffer), NOT timeseries API | Real-time, no polling, immediate updates for live 60s window |
| Next.js API proxy | `next.config.js` rewrites for all `/api/v1/*` REST calls | Avoids CORS on localhost; WebSocket connects directly (not subject to same CORS) |
| WS backoff formula | `Math.min(30000, 1000 * 2^attempt)` | Starts 1s, doubles: 1s → 2s → 4s → 8s → 16s → 30s cap |
| Max live table rows | 500 | Prevents memory growth during long monitoring sessions |
| Recharts animation | `isAnimationActive={false}` on all live charts | Prevents visual jitter on high-frequency live updates |
| CaptureStatus state machine | Three states only: `loading` / `active` / `unreachable` | `/api/v1/status` hardcodes `capture:"running"` while server is alive (routes/status.py:24). There is no `capture:"stopped"` response from a live backend. A poll failure renders `unreachable`, not "stopped" |
| First-run setup detection | Discovered from HTTP 503 on `POST /api/v1/auth/login`, not from `/api/v1/health` | `/api/v1/health` does not expose `needs_setup` (routes/status.py:44-50). The login endpoint returns `{ detail: "Run setup first" }` when unconfigured. Frontend always shows login form first; setup UI appears only after the 503 |
| AlertsPanel data ownership | `index.tsx` owns `alerts` state via initial `GET /api/v1/alerts` + WS push; `AlertsPanel` is display-only | Clear boundary: AlertsPanel never calls the alerts API. Actions (suppress/resolve) are the only internal REST calls |
| Verification shell | Windows `cmd` / PowerShell syntax | This repo runs on Windows; all plan shell commands use `cmd` or `powershell` syntax, not bash/grep |

---

## 4. Component → Requirement Traceability

| Component | Requirements Covered | Plan |
|-----------|---------------------|------|
| `hooks/useWebSocket.ts` | UI-06, UI-07, UI-10 | 06-01 |
| `hooks/useAuth.ts` + login page | AUTH-01, AUTH-04 (setup wizard) | 06-01 |
| `components/ConnectionsTable.tsx` | UI-01, UI-06 | 06-01 |
| `components/AlertsPanel.tsx` | UI-02, UI-07, UI-08 | 06-02 |
| `components/CaptureStatus.tsx` | UI-05 | 06-03 |
| `components/ConnectionsPerApp.tsx` | UI-03 | 06-03 |
| `components/ConnectionsPerSecond.tsx` | UI-04 | 06-03 |
| `components/AllowlistManager.tsx` | UI-09 | 06-03 |
| `components/SuppressionsLog.tsx` | SUPP-04 | 06-03 |
| `lib/api.ts` | API-01..13 (client side) | 06-01 |
| `lib/types.ts` | All data shapes | 06-01 |
| `pages/index.tsx` + layout | UI-11, overall dashboard | 06-01 |
| WS reconnect in `useWebSocket` | UI-10 (max 30s backoff) | 06-01 |
| Pause/resume in `useWebSocket` | UI-07 (pause toggle) | 06-02 |

---

## 5. Anti-Pattern Checklist

Before each wave merge, verify none of these are present:

- [ ] `connections.map((c) => <tr ...>)` JSX inside the live table (must use DOM mutation)
- [ ] `useState<WebSocket>` (must be `useRef<WebSocket>`)
- [ ] `import bootstrap from 'cdn...'` or `<link rel="stylesheet" href="https://...bootstrap...">` (must be npm import in `_app.tsx`)
- [ ] `app/` directory present in scaffold (Pages Router only — delete if it appears)
- [ ] Tailwind directives in `globals.css` (`@tailwind base` etc.)
- [ ] Direct fetch to `http://127.0.0.1:8001/api/v1/*` from client (must use `/api/v1/*` through Next.js proxy)
- [ ] WebSocket connected before JWT is resolved (token must be truthy before `connect()`)
- [ ] `isAnimationActive` absent from live Recharts components (must be `false`)
- [ ] No `MAX_ROWS = 500` guard in table DOM mutation

---

## 6. Open Questions (Resolved)

| Question | Resolution | Action |
|----------|-----------|--------|
| Backend port | Port 8001 (stated in context; uvicorn CLI flag) | Hard-code `127.0.0.1:8001` in `next.config.js` rewrites and `useWebSocket`; add `NEXT_PUBLIC_API_URL` env override |
| First-run setup wizard | Implement minimal setup screen — backend blocks login until setup | 06-01 includes login + setup pages |
| CPS chart data source | WS stream client-side buffer (Pattern 5 from research) | No timeseries API polling for live chart |
| CORS WebSocket | Native browser WS to `ws://127.0.0.1:8001` from `localhost:3000` is permissive for local origins | Validate during scaffold smoke test |

---

## 7. Environment Preconditions

| Precondition | Required By | How to Verify | Status |
|-------------|-------------|---------------|--------|
| Node.js ≥ 18 installed | Next.js 14 | `node --version` | Verified: Node 24.13.0 |
| npm ≥ 9 installed | Package installs | `npm --version` | Verified: npm 11.8.0 |
| Backend running at `http://127.0.0.1:8001` | E2E / UAT tests | `curl http://127.0.0.1:8001/api/v1/health` | Required at UAT time |
| PostgreSQL running on port 5433 | Backend DB reads | `psql -h localhost -p 5433 -U pnpg pnpg` | Required at UAT time |
| `data/auth.json` exists (or needs_setup=true) | Login flow | Backend state | Handled by setup wizard |

---

## 8. Validation Sign-off

**This document is valid when:**
- All Section 1 contract locks are confirmed against Phase 5 source (done)
- All Section 2 version locks are verified from npm registry (done)
- All Section 3 architecture decisions are documented (done)
- Section 5 checklist is referenced during wave merges

**Validation complete:** 2026-04-06
**Next step:** Execute 06-01-PLAN.md
