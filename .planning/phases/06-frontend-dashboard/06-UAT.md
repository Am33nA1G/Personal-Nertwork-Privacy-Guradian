---
status: pending
phase: 06-frontend-dashboard
source: [ROADMAP.md Phase 6 success criteria, 06-01-PLAN.md, 06-02-PLAN.md, 06-03-PLAN.md, 06-VALIDATION.md]
started: ~
updated: ~
---

# Phase 6 UAT: Frontend Dashboard

**Preconditions (must be TRUE before running UAT):**
- Backend running at `http://127.0.0.1:8001` (uvicorn with Phase 5 code)
- PostgreSQL running on port 5433, `pnpg` database accessible
- `data/auth.json` exists (password set up) OR backend `needs_setup: true` (setup wizard handles this)
- `npm --prefix frontend run dev` serving at `http://localhost:3000`
- All three plan test suites pass: `npm --prefix frontend test`

---

## Tests

### 1. Scaffold and stack locks
expected: |
  Run: `npm --prefix frontend list next react bootstrap recharts`
  Output must show: next@14.2.35, react@18.x, bootstrap@5.3.8, recharts@2.15.4
  Windows cmd check for pages dir:
    dir frontend\pages\ :: must show _app.tsx, index.tsx (no app directory)
  Windows cmd check for Tailwind directives (PowerShell):
    powershell -Command "if (Select-String -Path frontend\styles\globals.css -Pattern '@tailwind') { 'FOUND — FAIL' } else { 'CLEAN — PASS' }"
awaiting: pending
result: ~

### 2. Dark theme and Bootstrap loaded
expected: |
  Run: `npm --prefix frontend run build` — must exit 0 with no TypeScript errors.
  Manual: visit http://localhost:3000 — body background must be #0d1117 (dark), not white.
  DevTools: Elements panel — html[data-bs-theme=dark] attribute present.
  DevTools: Network — bootstrap.min.css loaded from node_modules (not CDN).
awaiting: pending
result: ~

### 3. First-run setup / login flow
expected: |
  Backend contract: POST /api/v1/auth/login returns HTTP 503 + { "detail": "Run setup first" }
  when no initial password is set. /api/v1/health does NOT expose needs_setup.
  The frontend always shows the login form first; setup UI appears only after the 503 response.

  Scenario A (backend needs_setup=true):
    1. Navigate to http://localhost:3000 — LOGIN form appears (not setup form yet)
    2. Enter any password and submit
    3. Backend returns 503 "Run setup first" — setup section now visible below login card
    4. Enter new password + confirm and submit — calls POST /api/v1/auth/setup
    5. On success, login called automatically — dashboard loads
  Scenario B (already configured):
    1. Navigate to http://localhost:3000 — login form appears
    2. Enter correct password — dashboard loads; WsStatusIndicator shows "● Live"
  Scenario C (wrong password):
    Enter wrong password — error message appears; no redirect
  Session persistence:
    Reload tab — dashboard loads automatically (token in sessionStorage)
    Close tab and reopen — login form appears again (sessionStorage cleared)
awaiting: pending
result: ~

### 4. Live connections table — delta update (UI-01, UI-06)
expected: |
  With backend running and traffic flowing:
  1. Dashboard — table visible with canonical 8 columns:
     Time | App | Domain | Country (flag emoji) | ASN | IP | Port | Protocol
     ("Severity" is NOT a table column — severity belongs in AlertsPanel only)
  2. Open browser DevTools → Elements → tbody inside the connections table
  3. Wait 2 seconds — new rows appear prepended at top WITHOUT tbody being replaced
  4. DevTools confirms DOM mutation is insertBefore/prepend, not innerHTML replacement
  5. Country column shows flag emoji: e.g., 🇺🇸 for US destinations
  6. ASN column shows e.g., "AS15169" or "—" when unavailable
  7. Blocklisted connection (if any) has table-danger (red) row highlight
  Verification command: `npm --prefix frontend test -- --testPathPattern="ConnectionsTable"`
awaiting: pending
result: ~

### 5. WebSocket reconnect with exponential backoff (UI-10)
expected: |
  1. Dashboard loads with WsStatusIndicator showing "● Live"
  2. Kill the uvicorn backend process (Ctrl+C)
  3. WsStatusIndicator changes to "✕ Disconnected" within 1s
  4. Indicator changes to "⟳ Connecting..." as reconnect attempts start
  5. Restart uvicorn  
  6. WsStatusIndicator returns to "● Live" within 30s (max backoff)
  7. New connection rows continue flowing into table after reconnect
  Browser console must show reconnect delay messages (1s, 2s, 4s...) — no unhandled exceptions.
  Verification command: `npm --prefix frontend test -- --testPathPattern="useWebSocket"`
awaiting: pending
result: ~

### 6. Alerts panel — severity colors and actions (UI-02, UI-08)
expected: |
  With active alerts in the backend:
  1. AlertsPanel shows new alerts within 1s of WS push (or from initial GET /api/v1/alerts)
  2. CRITICAL alert → left border var(--sev-critical) red; badge bg-danger
  3. HIGH/ALERT alert → left border var(--sev-alert) orange
  4. WARNING alert → left border var(--sev-warning) yellow; badge bg-warning text-dark
  5. Click "Suppress" on any alert → button shows spinner → alert disappears from panel
  6. Verify in backend: GET /api/v1/alerts?status=suppressed shows the alert as suppressed
  7. Click "Resolve" on a different alert → same disappear behavior
  8. Verify in backend: GET /api/v1/alerts?status=resolved shows that alert
  Verification command: `npm --prefix frontend test -- --testPathPattern="AlertsPanel"`
awaiting: pending
result: ~

### 7. Pause/resume toggle (UI-07)
expected: |
  1. Click "⏸ Pause" → button changes to "▶ Resume"; amber banner appears
  2. Watch table and alerts panel — no new rows or cards appear for 10+ seconds
  3. Browser WS inspector (DevTools → Network → WS) confirms server still sending frames
  4. Banner shows buffered event count increasing
  5. Click "Resume" → buffered rows and alerts flush into view at once
  6. WS continues without reconnect (WebSocket never closed during pause)
  Verification command: `npm --prefix frontend test -- --testPathPattern="useWebSocket"`
awaiting: pending
result: ~

### 8. Connections-per-app chart (UI-03)
expected: |
  1. Recharts BarChart visible below the main table/alerts row
  2. X-axis shows process names (chrome, python, etc.)
  3. Y-axis shows connection counts
  4. Chart updates as new connections accumulate (without page refresh)
  5. Top 10 processes shown maximum
  6. DevTools: no "window is not defined" errors — ssr: false dynamic import confirmed
  Verification command: `npm --prefix frontend test -- --testPathPattern="ConnectionsPerApp"`
awaiting: pending
result: ~

### 9. Connections-per-second rolling chart (UI-04)
expected: |
  1. Recharts LineChart visible beside the Per-App chart
  2. Shows rolling 60-second window of connection counts per second
  3. Chart advances in real time without page refresh
  4. Old data points (>60s) disappear from left side as new ones arrive on right
  5. No animation jitter on live updates (isAnimationActive={false} confirmed)
  Verification command: `npm --prefix frontend test -- --testPathPattern="ConnectionsPerSecond"`
awaiting: pending
result: ~

### 10. Capture status indicator (UI-05)
expected: |
  Backend contract: /api/v1/status always returns { capture: "running" } while the backend is alive.
  There is NO "stopped" response from a live API (routes/status.py:24 hardcodes "running").
  The CaptureStatus component has exactly three visual states: loading / active / unreachable.

  1. Navbar shows "● Active ({probe_type})" badge when backend is running
  2. Verify backend response (PowerShell):
     powershell -Command "(Invoke-WebRequest -H @{Authorization='Bearer TOKEN'} http://127.0.0.1:8001/api/v1/status | ConvertFrom-Json).data"
     Must show: capture='running'; probe_type='libpcap'; uptime=<float>
  3. Stop backend (kill uvicorn) — within 5s badge changes to "✕ Backend unreachable"
     (NOT "Stopped" — the fetch fails with a network error; component renders 'unreachable' state)
  4. Restart backend — badge returns to "● Active" within 5s (next poll cycle)
  Component test: `npm --prefix frontend test -- --testPathPattern="CaptureStatus"`
awaiting: pending
result: ~

### 11. Allowlist Manager — full CRUD (UI-09)
expected: |
  1. Navigate to http://localhost:3000/allowlist
  2. Existing rules table loads from GET /api/v1/allowlist
  3. Click "Add Rule" → form appears with fields: process name, dst IP, dst hostname, reason, expires
  4. Fill process_name="python.exe", dst_hostname="example.com" → submit
  5. New rule appears in table; verify: GET /api/v1/allowlist from backend shows it
  6. Click "Delete" on the new rule → rule disappears from table; verify backend confirms deletion
  7. Form validation: submit with empty dst_ip and empty dst_hostname → client error, no API call
  Verification command: `npm --prefix frontend test -- --testPathPattern="AllowlistManager"`
awaiting: pending
result: ~

### 12. Suppression Log with undo (SUPP-04)
expected: |
  1. Navigate to http://localhost:3000/allowlist
  2. Suppressions log visible below AllowlistManager
  3. Existing suppressions (from previous alert suppress actions) appear with: rule_id, process, scope, reason, timestamp
  4. Click "Undo" on a suppression → DELETE /api/v1/suppressions/:id called → entry removed from list
  5. Verify: GET /api/v1/suppressions from backend no longer contains that entry
  Verification command: `npm --prefix frontend test -- --testPathPattern="SuppressionsLog"`
awaiting: pending
result: ~

### 13. Automated test suite — full green
expected: |
  Run: `npm --prefix frontend test`
  All tests pass with 0 failures and 0 errors.
  Run: `npx tsc --noEmit --project frontend/tsconfig.json`
  Must exit 0 with no type errors.
  Run: `npm --prefix frontend run build`
  Must exit 0 (production build succeeds).
awaiting: pending
result: ~

### 14. Anti-pattern audit
expected: |
  All of the following checks must emit CLEAN (0 matches) for each item.
  PowerShell returns objects for each match; an empty result means no violations.

  1. No direct :8001 REST calls in lib/hooks/pages:
     powershell -Command "if (Select-String -Path frontend/lib/*.ts,frontend/hooks/*.ts,frontend/pages/*.tsx -Pattern '127.0.0.1:8001/api') { 'FAIL — direct backend call found' } else { 'CLEAN' }"

  2. No JSX map re-render in ConnectionsTable:
     powershell -Command "if (Select-String -Path frontend/components/ConnectionsTable.tsx -Pattern 'connections\.map') { 'FAIL — JSX map found in live table' } else { 'CLEAN' }"

  3. No useState for WebSocket instance:
     powershell -Command "if (Select-String -Path frontend/hooks/useWebSocket.ts -Pattern 'useState.*WebSocket') { 'FAIL — WS in state' } else { 'CLEAN' }"

  4. No CDN Bootstrap:
     powershell -Command "if (Select-String -Path frontend/pages/ -Pattern 'cdn.*bootstrap|bootstrap\.min\.css.*http' -Recurse) { 'FAIL — CDN Bootstrap found' } else { 'CLEAN' }"

  5. No Tailwind directives:
     powershell -Command "if (Select-String -Path frontend/styles/ -Pattern '@tailwind' -Recurse) { 'FAIL — Tailwind directive found' } else { 'CLEAN' }"

  6. isAnimationActive=false present in live chart:
     powershell -Command "Select-String -Path frontend/components/ConnectionsPerSecond.tsx -Pattern 'isAnimationActive' | Select-Object -First 1"
     The returned line must contain 'false'. If the command returns nothing, the attribute is absent — FAIL.
awaiting: pass
result: "PASS — All anti-pattern checks PASSED (CLEAN results for direct calls, JSX maps, WS state, CDN, Tailwind; isAnimationActive={false} verified)."

---

## Summary

total: 14
passed: 0
issues: 0
blocked: 0
skipped: 0
pending: 14

## Gaps

- Backend must be running for tests 3–12; these are manual/E2E steps requiring the full Phase 5 stack
- Rate limiting (API-11: 100 req/min) may slow UAT iteration — wait 60s between heavy test runs
