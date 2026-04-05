# Phase 6: Frontend Dashboard — Research

**Researched:** 2026-04-05
**Domain:** React 18 / Next.js 14 / Recharts / Bootstrap 5 / WebSocket client
**Confidence:** HIGH

---

## Summary

Phase 6 builds the React 18 / Next.js 14 dashboard that consumes the backend built in Phase 5. The backend WebSocket contract is fully known from source inspection: the server pushes `{ "type": "batch", "events": [...] }` frames every 500ms where each event object contains a `connections` array and an `alerts` array; heartbeats arrive as `{ "type": "heartbeat", "ts": <float> }`. Authentication is JWT-based — the token must be acquired via `POST /api/v1/auth/login` and passed as a `?token=<jwt>` query parameter on the WebSocket URL.

The key architectural decision is Next.js App Router vs Pages Router. For a single-screen monitoring dashboard there is no multi-page routing requirement, but App Router enables React Server Components which are actively harmful for this use case (all content is live-updated via WebSocket client state). Pages Router with a single `pages/index.tsx` is the cleaner choice: no RSC complexity, simpler layout, direct `useEffect` WebSocket setup with no hydration surprises.

No existing frontend directory is present in the repo. The scaffold must be created from scratch under `frontend/` using `create-next-app@14`. Bootstrap 5 must be imported via npm (not CDN — CLAUDE.md is explicit). The visual direction is dark-theme, data-dense, purpose-built for a security monitoring tool — not a generic admin panel.

**Primary recommendation:** Pages Router, single-page layout with dark Bootstrap 5 theme, useRef table for delta row injection, useReducer for alert/connection state, and a custom WebSocket hook with exponential backoff. No Redux, no animation libraries, no additional state management packages.

---

## Project Constraints (from CLAUDE.md)

**Mandatory — no substitutions permitted:**

- React 18.x (not 19.x — Next.js 14.2.x requires `^18.2.0`)
- Next.js 14.x (pinned to 14.2.x — latest stable in the 14 line is 14.2.35)
- Recharts 2.x (React-native charting; latest in series is 2.15.4)
- Bootstrap 5 (via npm, not CDN; Bootstrap 5.3.x; no jQuery)
- Native WebSocket API (browser built-in) — no socket.io, no reconnecting-websocket packages
- No Redux — use React state / context only
- Backend runs at `http://127.0.0.1:8001` (set at uvicorn launch time; not in config.yaml)
- JWT auth: `POST /api/v1/auth/login` → `{ data: { access_token, refresh_token, token_type } }`
- GSD Workflow Enforcement: use `/gsd:execute-phase` entry point, not direct file edits

---

## Backend Contract (verified from source)

### WebSocket: `/api/v1/ws/live?token=<jwt>`

**Connection:** Authenticate via query param `?token=<jwt>`. Server closes with code 4001 on auth failure.

**Inbound frames from server:**

```json
// Batch frame (every 500ms, up to 100 events per flush)
{
  "type": "batch",
  "events": [
    {
      "connections": [<ConnectionObject>],
      "alerts": [<AlertObject>]
    }
  ]
}

// Heartbeat frame (every 10s)
{
  "type": "heartbeat",
  "ts": 1712345678.123
}
```

**Important:** `events` is an array of broadcast payloads. Each payload has a `connections` array and an `alerts` array. The client must iterate `events` and for each, spread `connections` and `alerts` into their respective state arrays.

**Outbound (client → server):**

```json
// Client-side filter (optional)
{ "type": "filter", "data": { "process": "chrome.exe" } }
```

### Connection Object (full schema from REQUIREMENTS.md)

```json
{
  "event_id": "uuid",
  "timestamp": "ISO8601",
  "process_name": "chrome.exe",
  "pid": 1234,
  "src_ip": "192.168.1.5",
  "src_port": 52341,
  "dst_ip": "142.250.183.14",
  "dst_hostname": "google.com",
  "dst_country": "US",
  "dst_asn": "AS15169",
  "dst_org": "Google LLC",
  "dst_port": 443,
  "protocol": "TCP",
  "bytes_sent": 1240,
  "bytes_recv": 8800,
  "state": "ESTABLISHED",
  "threat_intel": { "is_blocklisted": false, "source": null },
  "severity": "INFO"
}
```

### Alert Object (full schema from REQUIREMENTS.md)

```json
{
  "alert_id": "uuid",
  "timestamp": "ISO8601",
  "severity": "HIGH",
  "rule_id": "DET-02",
  "reason": "chrome exceeded 100 connections/min",
  "confidence": 0.91,
  "process_name": "chrome",
  "pid": 4821,
  "dst_ip": "93.184.216.34",
  "dst_hostname": "example.com",
  "recommended_action": "REVIEW",
  "suppressed": false
}
```

### REST API Shapes (verified from source)

**Login:**
```
POST /api/v1/auth/login
Body: { "password": "<string>" }
Response: { "data": { "access_token": "...", "refresh_token": "...", "token_type": "bearer" } }
```

**Connections:**
```
GET /api/v1/connections?page=1&page_size=50
Headers: Authorization: Bearer <token>
Response: { "data": [...], "pagination": { "page", "page_size", "total" } }
```

**Alerts:**
```
GET /api/v1/alerts?status=active
Headers: Authorization: Bearer <token>
Response: { "data": [...], "pagination": { ... } }

PATCH /api/v1/alerts/:alert_id
Body: { "action": "suppress"|"resolve", "reason": "optional" }
Response: { "data": <updatedAlert> }
```

**Allowlist:**
```
GET /api/v1/allowlist
Response: { "data": [<AllowlistRule>] }

POST /api/v1/allowlist
Body: { "process_name"?: string, "dst_ip"?: string, "dst_hostname"?: string, "expires_at"?: ISO8601, "reason"?: string }
Response: { "data": <createdRule> }

DELETE /api/v1/allowlist/:rule_id
Response: { "data": { "deleted": true } }
```

**Suppressions (SUPP-04 — suppression log with undo):**
```
GET /api/v1/suppressions
Response: { "data": [<Suppression>] }

DELETE /api/v1/suppressions/:suppression_id
Response: { "data": { "deleted": true } }
```

**Stats:**
```
GET /api/v1/stats/summary
Response: { "data": { "total_connections", "unique_destinations", "active_alerts", "top_processes", "top_destinations" } }

GET /api/v1/stats/timeseries?metric=connections&interval=1m
Response: { "data": [{ bucket, count }] }
```

**Status:**
```
GET /api/v1/status
Response: { "data": { "capture": "running"|"stopped", "interface": string, "uptime": float, "probe_type": string } }
```

**Health (no auth):**
```
GET /api/v1/health
Response: { "data": { "status": "ok", "probe": string, "db": "ok"|"unavailable", "stream": "ok" } }
```

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Live connections table: Time, App, Domain, Country, IP, Port, Protocol, Flag columns | Connection object has all needed fields; `dst_country` → flag emoji via lookup table |
| UI-02 | Alerts panel with severity color coding (WARNING=yellow, ALERT=orange, CRITICAL=red) | Alert object has `severity` field; Bootstrap badge/border-left color classes |
| UI-03 | Recharts connections-per-app bar or donut chart | Derive from connection state; `process_name` → count aggregation in component |
| UI-04 | Recharts connections-per-second rolling 60s window line chart | Maintain `useRef` circular buffer of `{ ts, count }` entries; trim entries older than 60s on each frame |
| UI-05 | Capture status indicator: Active/Stopped + capture method | `GET /api/v1/status` polled every 5s; `probe_type` field available |
| UI-06 | WebSocket delta updates — no full DOM re-render | `useRef` on rows array + `prepend` to table body DOM node; do NOT use `rows.map(...)` JSX re-render |
| UI-07 | Pause/resume toggle halts live UI updates without disconnecting WebSocket | `isPaused` state ref; when paused, enqueue to a pending buffer; resume flushes buffer |
| UI-08 | Alerts panel: Suppress and Resolve buttons per alert | `PATCH /api/v1/alerts/:id` with `{ action: "suppress" }` or `{ action: "resolve" }` |
| UI-09 | Allowlist Manager: view, add, delete rules | `GET/POST/DELETE /api/v1/allowlist` — all shapes confirmed |
| UI-10 | WebSocket exponential backoff reconnect (max 30s) + connection status indicator | Custom hook; backoff: `Math.min(30000, base * 2^attempt)` |
| UI-11 | Built with React 18 / Next.js 14 | Scaffold with `create-next-app@14.2.35 --no-tailwind --no-app --ts` |
| SUPP-04 | Suppression log viewable in dashboard with undo | `GET /api/v1/suppressions` + `DELETE /api/v1/suppressions/:id`; render in Allowlist Manager or dedicated tab |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| next | 14.2.35 | React framework + dev server | Locked in CLAUDE.md; 14.2.x is the latest patched 14 series release |
| react | 18.3.1 | UI runtime | Locked in CLAUDE.md; 18.3.1 is latest React 18 — Next.js 14 peer requires `^18.2.0` |
| react-dom | 18.3.1 | DOM renderer | Paired with react; same version |
| recharts | 2.15.4 | Data visualization | Locked in CLAUDE.md; 2.15.4 is latest stable in the 2.x series |
| bootstrap | 5.3.8 | UI components and layout | Locked in CLAUDE.md; install via npm |
| typescript | 5.x (bundled by Next.js) | Type safety | Next.js 14 bundles its own TS; do not add separately |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @types/react | 18.x | TypeScript types for React | Always — enables type checking |
| @types/react-dom | 18.x | TypeScript types for react-dom | Always — paired with @types/react |
| @types/node | 20.x | TypeScript types for Node.js | Needed for Next.js config types |

### Alternatives Considered (for context — NOT choices)
| Instead of | Could Use | Why Not |
|------------|-----------|---------|
| Pages Router | App Router | App Router adds RSC complexity with zero benefit for a single-screen WebSocket client; Pages Router is simpler and avoids "use client" boilerplate on every component |
| Bootstrap 5 | Tailwind CSS | CLAUDE.md says Bootstrap 5; no substitution |
| Native WebSocket | reconnecting-websocket package | CLAUDE.md says native WebSocket API; custom hook handles backoff |
| No Redux | Zustand / Redux Toolkit | CLAUDE.md says no Redux; React state + context is sufficient |

### Installation

```bash
cd frontend
npx create-next-app@14.2.35 . --typescript --no-tailwind --no-app --no-src-dir --eslint --import-alias "@/*"
npm install bootstrap@5.3.8 recharts@2.15.4
npm install --save-dev @types/node
```

---

## Architecture Patterns

### Recommended Project Structure

```
frontend/
├── pages/
│   ├── _app.tsx          # Bootstrap CSS import, global providers
│   ├── index.tsx         # Main dashboard page (single screen)
│   └── allowlist.tsx     # Allowlist Manager screen
├── components/
│   ├── ConnectionsTable.tsx    # Live table with delta-update DOM writes
│   ├── AlertsPanel.tsx         # Alert list + suppress/resolve actions
│   ├── ConnectionsPerApp.tsx   # Recharts BarChart
│   ├── ConnectionsPerSecond.tsx # Recharts LineChart rolling 60s
│   ├── CaptureStatus.tsx       # Status indicator pill
│   ├── AllowlistManager.tsx    # CRUD for allowlist rules
│   └── SuppressionsLog.tsx     # SUPP-04: suppression log with undo
├── hooks/
│   ├── useWebSocket.ts   # WS connection, auth, reconnect backoff
│   └── useAuth.ts        # JWT storage, login, token refresh
├── lib/
│   ├── api.ts            # fetch wrappers for all REST endpoints
│   ├── types.ts          # TypeScript interfaces for all data shapes
│   └── countryFlag.ts    # ISO 3166-1 alpha-2 → flag emoji lookup
├── styles/
│   └── globals.css       # Dark theme overrides on Bootstrap variables
└── next.config.js        # rewrites: /api/v1/* → http://127.0.0.1:8001/api/v1/*
```

### Pattern 1: Pages Router with Single Dashboard Page

Use `--no-app` flag in `create-next-app`. The entire monitoring UI lives in `pages/index.tsx`. Routing to the Allowlist Manager uses `next/link` to `pages/allowlist.tsx`.

```tsx
// pages/_app.tsx
import 'bootstrap/dist/css/bootstrap.min.css';
import '../styles/globals.css';
import type { AppProps } from 'next/app';

export default function App({ Component, pageProps }: AppProps) {
  return <Component {...pageProps} />;
}
```

### Pattern 2: WebSocket Custom Hook with Exponential Backoff

The hook maintains the WS instance in a ref (not state) to prevent re-renders on reconnect. Backoff starts at 1s, doubles each attempt, caps at 30s.

```tsx
// hooks/useWebSocket.ts
import { useEffect, useRef, useCallback, useState } from 'react';

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

export function useWebSocket(
  token: string | null,
  onBatch: (events: any[]) => void
) {
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');

  const connect = useCallback(() => {
    if (!token) return;
    setStatus('connecting');
    const ws = new WebSocket(
      `ws://127.0.0.1:8001/api/v1/ws/live?token=${token}`
    );
    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      setStatus('connected');
    };

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'batch') onBatch(msg.events);
      // heartbeat: ignore
    };

    ws.onclose = () => {
      setStatus('disconnected');
      const delay = Math.min(MAX_DELAY_MS, BASE_DELAY_MS * 2 ** attemptRef.current);
      attemptRef.current += 1;
      setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, [token, onBatch]);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  return { status, ws: wsRef };
}
```

### Pattern 3: Delta Row Injection for Live Table (UI-06)

Do NOT derive table rows via `rows.map(...)` JSX — that re-renders the entire table on every push. Instead maintain a `useRef` on the `<tbody>` DOM node and prepend rows imperatively. Limit the live buffer to the most recent 500 rows via a `deque`-style splice.

```tsx
// components/ConnectionsTable.tsx
const tbodyRef = useRef<HTMLTableSectionElement>(null);
const rowCountRef = useRef(0);
const MAX_ROWS = 500;

function injectRows(connections: ConnectionEvent[]) {
  const tbody = tbodyRef.current;
  if (!tbody) return;

  connections.forEach((conn) => {
    const tr = document.createElement('tr');
    tr.className = conn.threat_intel?.is_blocklisted ? 'table-danger' : '';
    tr.innerHTML = `
      <td>${new Date(conn.timestamp).toLocaleTimeString()}</td>
      <td>${conn.process_name}</td>
      <td>${conn.dst_hostname ?? conn.dst_ip}</td>
      <td>${countryFlag(conn.dst_country)}</td>
      <td>${conn.dst_ip}</td>
      <td>${conn.dst_port}</td>
      <td>${conn.protocol}</td>
      <td>${conn.severity}</td>
    `;
    tbody.prepend(tr);
    rowCountRef.current += 1;
  });

  // Trim to MAX_ROWS
  while (rowCountRef.current > MAX_ROWS && tbody.lastChild) {
    tbody.removeChild(tbody.lastChild);
    rowCountRef.current -= 1;
  }
}
```

### Pattern 4: Pause/Resume Toggle (UI-07)

The WebSocket stays connected. A `isPausedRef` (ref, not state — to avoid re-renders) gates whether new events are processed. While paused, incoming events accumulate in a `pendingRef` buffer. On resume, flush the buffer then clear it.

```tsx
const isPausedRef = useRef(false);
const pendingRef = useRef<any[]>([]);

function handleBatch(events: any[]) {
  if (isPausedRef.current) {
    pendingRef.current.push(...events);
    return;
  }
  processEvents(events);
}

function resume() {
  isPausedRef.current = false;
  processEvents(pendingRef.current);
  pendingRef.current = [];
}
```

### Pattern 5: Recharts Rolling 60s Line Chart (UI-04)

Maintain a `useRef` circular buffer of `{ ts: number, count: number }` entries. On each WebSocket batch, push a new entry and drop entries older than 60 seconds. Feed the ref's current value to Recharts via state (update state at 1Hz to avoid Recharts re-rendering every 500ms push).

```tsx
const bufferRef = useRef<{ ts: number; count: number }[]>([]);

// Called on each WS batch:
function updateCpsBuffer(connectionCount: number) {
  const now = Date.now();
  bufferRef.current.push({ ts: now, count: connectionCount });
  const cutoff = now - 60_000;
  bufferRef.current = bufferRef.current.filter((e) => e.ts >= cutoff);
}

// Sync to Recharts state at 1Hz via setInterval:
const [chartData, setChartData] = useState<{ ts: number; count: number }[]>([]);
useEffect(() => {
  const id = setInterval(() => setChartData([...bufferRef.current]), 1000);
  return () => clearInterval(id);
}, []);
```

### Pattern 6: JWT Storage for Local-Only Single-User Tool

**Decision: sessionStorage.** This is a local-only tool with no sensitive user data exposed through the token (single-user, `sub: "pnpg-user"`). Storing in memory requires re-login on every page refresh, which is poor UX for a monitoring dashboard. localStorage persists across tabs and survives browser restart — too long-lived for an 8-hour token. sessionStorage survives page refresh within the same tab, expires on tab close, and matches the 8-hour JWT expiry lifecycle. This is the right choice for this use case.

```tsx
// On login:
sessionStorage.setItem('pnpg_token', data.access_token);

// On load:
const token = sessionStorage.getItem('pnpg_token');
```

### Pattern 7: Next.js API Proxy to Backend

Configure `next.config.js` rewrites so the frontend never exposes the backend address in client-side fetch calls and CORS is avoided entirely:

```js
// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://127.0.0.1:8001/api/v1/:path*',
      },
    ];
  },
};
module.exports = nextConfig;
```

WebSocket cannot use HTTP rewrites; the WS client connects directly to `ws://127.0.0.1:8001/api/v1/ws/live?token=...`.

### Pattern 8: Dark Theme with Bootstrap 5

Bootstrap 5.3+ supports `data-bs-theme="dark"` natively. Set it on `<html>`:

```tsx
// pages/_document.tsx
import { Html, Head, Main, NextScript } from 'next/document';
export default function Document() {
  return (
    <Html data-bs-theme="dark" lang="en">
      <Head />
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
```

Override Bootstrap CSS variables in `globals.css` for the security-tool aesthetic (darker background, higher contrast accent colors for severity levels):

```css
/* styles/globals.css */
:root[data-bs-theme="dark"] {
  --bs-body-bg: #0d1117;
  --bs-body-color: #c9d1d9;
  --bs-border-color: #30363d;
  /* severity accents */
  --sev-warning: #e3b341;
  --sev-alert: #f0883e;
  --sev-critical: #f85149;
  --sev-info: #58a6ff;
}
```

### Anti-Patterns to Avoid

- **Full table re-render on each WS push:** Using `connections.map((c) => <tr key={c.event_id}>...)` in JSX will cause the entire table to re-render 2x per second. Use DOM mutation (Pattern 3) for the live table.
- **Storing WS instance in React state:** Causes infinite reconnect loops. Store in `useRef`.
- **Calling API on every row render:** Severity color mapping must be pure/derived, not fetched.
- **Forgetting the first-run setup wizard:** The backend requires `POST /api/v1/auth/setup` before login is possible (`needs_setup` flag). The frontend must check `GET /api/v1/health` first; if the login endpoint returns 503 "Run setup first", show the setup form (one-time password entry).
- **Using CDN Bootstrap:** CLAUDE.md requires npm import. CDN blocks Next.js SSR and FOUC.
- **Tailwind defaults from create-next-app:** Use `--no-tailwind` flag; Tailwind conflicts with Bootstrap.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Country flag display | Custom flag image spritesheet | ISO 3166-1 alpha-2 → Unicode flag emoji (e.g., "US" → "🇺🇸") | Two-letter code to regional indicator symbols is a 3-line pure function; no library needed |
| Chart data | Custom canvas drawing | Recharts `<BarChart>`, `<LineChart>` | Recharts handles responsive sizing, tooltip, animation, axes |
| HTTP client | `fetch` wrapper from scratch | Simple `lib/api.ts` with `Authorization` header injection | No Axios needed; fetch is adequate for this REST surface |
| WebSocket reconnect library | Custom retry library | The `useWebSocket` hook (Pattern 2 above) | The pattern is 30 lines; no package worth the dependency |
| Date formatting | moment.js / date-fns | `toLocaleTimeString()` / `new Date(ts).toISOString()` | Native Date is sufficient for timestamp display |

**Key insight:** This is a data display app, not a form-heavy app. The complexity is in the live update pattern and WebSocket lifecycle, not in UI components — resist adding component libraries.

---

## Common Pitfalls

### Pitfall 1: WebSocket Authentication Timing Race

**What goes wrong:** The component mounts and tries to open a WebSocket before the JWT is available (login hasn't completed yet).
**Why it happens:** Login is async; if `useWebSocket` runs immediately on mount, `token` is null.
**How to avoid:** Pass `token` as a dependency; the hook's `useEffect` only runs `connect()` if `token` is truthy. Show a login screen if `token` is null.
**Warning signs:** WebSocket closes with code 4001 immediately on load.

### Pitfall 2: `create-next-app` Defaults

**What goes wrong:** Running `create-next-app` without flags installs Tailwind CSS (conflicts with Bootstrap) and creates the App Router directory structure (`app/` folder).
**Why it happens:** Next.js 14 defaults are `--tailwind --app`.
**How to avoid:** Always use `--no-tailwind --no-app` flags. Verify no `app/` directory was created.
**Warning signs:** `globals.css` contains Tailwind directives; `app/` directory exists.

### Pitfall 3: Bootstrap CSS Not Loading in Next.js

**What goes wrong:** Bootstrap classes have no effect; the page renders unstyled.
**Why it happens:** Bootstrap CSS must be imported in `pages/_app.tsx`, not in individual components.
**How to avoid:** `import 'bootstrap/dist/css/bootstrap.min.css'` in `_app.tsx` only.
**Warning signs:** All text renders without styling; dev tools show no Bootstrap rules.

### Pitfall 4: Recharts SSR Error

**What goes wrong:** `ReferenceError: window is not defined` or hydration mismatch errors with Recharts.
**Why it happens:** Recharts reads `window` on import; Next.js attempts SSR of chart components.
**How to avoid:** Wrap chart components in dynamic import with `{ ssr: false }`:
```tsx
import dynamic from 'next/dynamic';
const ConnectionsPerApp = dynamic(
  () => import('../components/ConnectionsPerApp'),
  { ssr: false }
);
```
**Warning signs:** Server-side error in Next.js logs mentioning `window`; chart doesn't render.

### Pitfall 5: Memory Leak from Unbounded Connection Array

**What goes wrong:** After hours of use, the connection state array has tens of thousands of items, causing slow renders and high memory usage.
**Why it happens:** Each WS push prepends new connections without pruning old ones.
**How to avoid:** Enforce `MAX_ROWS = 500` in the DOM mutation approach (Pattern 3). The connections array in React state (used for charts) should only hold the last 500 events.
**Warning signs:** Browser memory grows steadily; tab becomes sluggish after 30+ minutes.

### Pitfall 6: First-Run Setup Not Handled

**What goes wrong:** User opens dashboard, tries to log in, gets 503 "Run setup first" from the backend.
**Why it happens:** The backend requires `POST /api/v1/auth/setup` to set the initial password before `POST /api/v1/auth/login` works.
**How to avoid:** The login page must call `GET /api/v1/health` on mount; if health shows `db: "ok"` and login returns 503, render a "Set up your password" form that calls `POST /api/v1/auth/setup`.
**Warning signs:** Login always fails with 503 on fresh install.

### Pitfall 7: CORS Errors with Direct Backend Calls

**What goes wrong:** Browser blocks API calls to `http://127.0.0.1:8001/api/v1/...` from the Next.js dev server at `http://localhost:3000`.
**Why it happens:** Different ports = different origins = CORS policy applies.
**How to avoid:** Use Next.js `rewrites()` in `next.config.js` (Pattern 7) to proxy all `/api/v1/*` through the Next.js server. WebSocket must still connect directly — browser WS API is not subject to the same CORS restrictions as fetch for local origins, but confirm backend allows the WS upgrade.
**Warning signs:** Network tab shows CORS preflight failures on REST calls.

---

## Code Examples

### Recharts BarChart for Connections-per-App

```tsx
// Source: Recharts 2.x official docs + pattern from recharts.org
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

interface AppCount { name: string; count: number; }

export function ConnectionsPerApp({ data }: { data: AppCount[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <XAxis dataKey="name" tick={{ fill: '#c9d1d9', fontSize: 11 }} />
        <YAxis tick={{ fill: '#c9d1d9', fontSize: 11 }} />
        <Tooltip
          contentStyle={{ background: '#161b22', border: '1px solid #30363d' }}
        />
        <Bar dataKey="count" fill="#58a6ff" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

### Recharts LineChart for Connections-per-Second

```tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export function ConnectionsPerSecond({ data }: { data: { ts: number; count: number }[] }) {
  const formatted = data.map((d) => ({
    time: new Date(d.ts).toLocaleTimeString(),
    count: d.count,
  }));
  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={formatted}>
        <XAxis dataKey="time" tick={{ fill: '#c9d1d9', fontSize: 10 }} />
        <YAxis tick={{ fill: '#c9d1d9', fontSize: 10 }} />
        <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d' }} />
        <Line
          type="monotone"
          dataKey="count"
          stroke="#58a6ff"
          dot={false}
          strokeWidth={2}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

`isAnimationActive={false}` is critical for live-updating charts — Recharts animation causes visual jitter when data changes every second.

### Severity Color Mapping

```ts
// lib/types.ts
export const SEVERITY_CLASSES: Record<string, string> = {
  INFO:     'text-info',
  WARNING:  'text-warning',    // yellow
  ALERT:    'text-pnpg-alert', // custom: --sev-alert orange
  HIGH:     'text-pnpg-alert',
  CRITICAL: 'text-danger',     // red
  LOW:      'text-secondary',
};

export const SEVERITY_BADGE: Record<string, string> = {
  INFO:     'bg-info',
  WARNING:  'bg-warning text-dark',
  ALERT:    'bg-pnpg-alert',
  HIGH:     'bg-pnpg-alert',
  CRITICAL: 'bg-danger',
  LOW:      'bg-secondary',
};
```

### Country Flag from ISO Code

```ts
// lib/countryFlag.ts
export function countryFlag(code: string | null | undefined): string {
  if (!code || code.length !== 2) return '—';
  const offset = 127397; // 'A'.codePointAt(0)! - 65 + offset = regional indicator A
  return String.fromCodePoint(
    code.toUpperCase().charCodeAt(0) + offset,
    code.toUpperCase().charCodeAt(1) + offset,
  );
}
// countryFlag('US') → '🇺🇸'
// countryFlag('GB') → '🇬🇧'
// countryFlag(null) → '—'
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Vanilla JS + Chart.js | React 18 + Recharts | PRD upgrade 2026-04-04 | Allowlist Manager and alert actions require component state management |
| CDN Bootstrap | npm Bootstrap 5 | PRD upgrade 2026-04-04 | Proper bundling, no FOUC, SSR-safe |
| Next.js App Router (new default) | Pages Router (explicit choice for this project) | Next.js 13+ introduced App Router | App Router is default-on in create-next-app but wrong for a single-screen WS client |
| `data-bs-theme` not available | Bootstrap 5.3+ native dark mode | Bootstrap 5.3 (2023) | No custom CSS needed for dark theme base |
| Recharts animations on live data | `isAnimationActive={false}` | Best practice for streaming data | Prevents visual jitter on high-frequency updates |

---

## Open Questions

1. **Backend port confirmation**
   - What we know: Additional context states port 8001; no explicit port config found in config.yaml or pnpg source
   - What's unclear: Port is set at uvicorn launch time (CLI flag or script); not in config.yaml
   - Recommendation: Document as 8001 in `next.config.js` rewrites and `useWebSocket` hook; add a `NEXT_PUBLIC_API_URL` env var override for flexibility

2. **First-run setup flow UX depth**
   - What we know: Backend has `POST /api/v1/auth/setup` endpoint; `needs_setup` state exists on app
   - What's unclear: Whether Phase 6 should implement the full first-run wizard (password entry UI) or just document it
   - Recommendation: Implement a minimal setup screen — the backend blocks login until setup is done; a blank dashboard with "Login failed" is a poor experience

3. **`GET /api/v1/stats/timeseries` for rolling 60s CPS chart**
   - What we know: The timeseries endpoint exists with `interval=1m`; it returns historical data from PostgreSQL
   - What's unclear: Whether the live CPS chart should use the WS stream (real-time, computed client-side) or poll the timeseries API
   - Recommendation: Use WS stream for the live 60s rolling window (client-side, no API calls, immediate updates); use timeseries API for any historical view needed in the future

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Node.js | Next.js build/dev | Yes | 24.13.0 | — |
| npm | Package install | Yes | 11.8.0 | — |
| next@14.2.35 | Frontend scaffold | Not installed (fresh) | — | `npx create-next-app@14.2.35` installs it |
| react@18.3.1 | UI runtime | Not installed | — | Installed by create-next-app |
| recharts@2.15.4 | Charts | Not installed | — | `npm install recharts@2.15.4` |
| bootstrap@5.3.8 | Styling | Not installed | — | `npm install bootstrap@5.3.8` |
| Backend at :8001 | API / WebSocket | Unknown (Phase 5 complete) | — | Planner must note: backend must be running for E2E tests |

**Missing dependencies with no fallback:**
- None — all installs are via npm which is available.

**Missing dependencies with fallback:**
- Backend process: required for live testing; fallback for unit/component tests is mocked fetch responses.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Jest + React Testing Library (bundled via Next.js 14) |
| Config file | `frontend/jest.config.ts` — Wave 0 gap, must be created |
| Quick run command | `npm --prefix frontend test -- --testPathPattern="components" --passWithNoTests` |
| Full suite command | `npm --prefix frontend test` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | ConnectionsTable renders correct column headers | unit | `npm --prefix frontend test -- --testPathPattern="ConnectionsTable"` | Wave 0 |
| UI-02 | AlertsPanel applies severity CSS classes | unit | `npm --prefix frontend test -- --testPathPattern="AlertsPanel"` | Wave 0 |
| UI-03 | ConnectionsPerApp renders with data | unit | `npm --prefix frontend test -- --testPathPattern="ConnectionsPerApp"` | Wave 0 |
| UI-04 | ConnectionsPerSecond rolling buffer trims entries older than 60s | unit | `npm --prefix frontend test -- --testPathPattern="ConnectionsPerSecond"` | Wave 0 |
| UI-05 | CaptureStatus renders "Active" when status.capture == "running" | unit | `npm --prefix frontend test -- --testPathPattern="CaptureStatus"` | Wave 0 |
| UI-06 | Delta inject: table DOM rows increase on batch push, no full re-render | unit | `npm --prefix frontend test -- --testPathPattern="ConnectionsTable"` | Wave 0 |
| UI-07 | Pause: no new rows injected while paused; resume flushes buffer | unit | `npm --prefix frontend test -- --testPathPattern="useWebSocket"` | Wave 0 |
| UI-08 | AlertsPanel Suppress button calls PATCH with action="suppress" | unit | `npm --prefix frontend test -- --testPathPattern="AlertsPanel"` | Wave 0 |
| UI-09 | AllowlistManager: delete button calls DELETE /api/v1/allowlist/:id | unit | `npm --prefix frontend test -- --testPathPattern="AllowlistManager"` | Wave 0 |
| UI-10 | useWebSocket reconnects with delay after close; delay doubles each attempt | unit | `npm --prefix frontend test -- --testPathPattern="useWebSocket"` | Wave 0 |
| UI-11 | `pages/index.tsx` renders without error (smoke) | smoke | `npm --prefix frontend test -- --testPathPattern="index"` | Wave 0 |
| SUPP-04 | SuppressionsLog renders entries; undo calls DELETE /api/v1/suppressions/:id | unit | `npm --prefix frontend test -- --testPathPattern="SuppressionsLog"` | Wave 0 |

### Sampling Rate

- **Per task commit:** `npm --prefix frontend test -- --passWithNoTests`
- **Per wave merge:** `npm --prefix frontend test`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `frontend/jest.config.ts` — Jest config for Next.js with jsdom environment
- [ ] `frontend/jest.setup.ts` — `@testing-library/jest-dom` import
- [ ] `frontend/components/__tests__/ConnectionsTable.test.tsx` — covers UI-01, UI-06
- [ ] `frontend/components/__tests__/AlertsPanel.test.tsx` — covers UI-02, UI-08
- [ ] `frontend/components/__tests__/ConnectionsPerApp.test.tsx` — covers UI-03
- [ ] `frontend/components/__tests__/ConnectionsPerSecond.test.tsx` — covers UI-04
- [ ] `frontend/components/__tests__/CaptureStatus.test.tsx` — covers UI-05
- [ ] `frontend/components/__tests__/AllowlistManager.test.tsx` — covers UI-09
- [ ] `frontend/components/__tests__/SuppressionsLog.test.tsx` — covers SUPP-04
- [ ] `frontend/hooks/__tests__/useWebSocket.test.ts` — covers UI-07, UI-10
- [ ] Framework install: `npm install --save-dev jest @testing-library/react @testing-library/jest-dom jest-environment-jsdom`

---

## Sources

### Primary (HIGH confidence)

- npm registry (`npm view`) — verified exact package versions: next@14.2.35, react@18.3.1, recharts@2.15.4, bootstrap@5.3.8
- `pnpg/ws/manager.py` (source inspection) — exact WS frame shapes: `{ type: "batch", events: [...] }`, `{ type: "heartbeat", ts: float }`
- `pnpg/pipeline/worker.py` (source inspection) — broadcast payload shape: `{ connections: [event], alerts: alerts }`
- `pnpg/api/routes/*.py` (source inspection) — all REST endpoint shapes, query params, response envelopes
- `pnpg/api/auth.py` (source inspection) — JWT structure: HS256, `sub: "pnpg-user"`, 8h expiry; setup flow
- REQUIREMENTS.md — Connection and Alert object schemas (full field list)
- Bootstrap 5.3 docs — `data-bs-theme="dark"` native dark mode (available since 5.3.0)

### Secondary (MEDIUM confidence)

- Next.js 14 create-next-app CLI help (`npx create-next-app@14 --help`) — confirmed `--no-app`, `--no-tailwind` flags exist
- npm peer dependency check (`npm view next@14.2.35 peerDependencies`) — confirmed React 18.2.0 requirement
- Recharts 2.x patterns — `isAnimationActive={false}` for live data is documented in Recharts GitHub issues and community usage; verified against training knowledge

### Tertiary (LOW confidence)

- CORS behavior for WebSocket from Next.js dev server to same-host backend — assumed permissive for localhost; should be validated during scaffold testing

---

## Metadata

**Confidence breakdown:**
- Backend contract (WS shape, REST shapes): HIGH — verified from source code
- Standard stack (versions): HIGH — verified from npm registry
- Architecture patterns (Pages Router choice, delta injection): HIGH — grounded in React fundamentals and Next.js docs
- Delta row injection pattern (DOM mutation): MEDIUM — established pattern but depends on React not interfering with ref'd DOM nodes
- JWT sessionStorage recommendation: HIGH — rationale is sound for local-only single-user tool
- Test setup (Jest + RTL in Next.js 14): MEDIUM — standard setup but Next.js 14 `jest.config.ts` setup requires specific `next/jest` transformer

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable libraries; Next.js 14 line is in maintenance, unlikely to change)
