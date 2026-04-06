---
phase: 06-frontend-dashboard
plan: 01
subsystem: scaffold-and-live-table
tags: [nextjs, react, websocket, auth, bootstrap, typescript]
dependency_graph:
  requires:
    - phase-05: JWT auth endpoints, WebSocket /api/v1/ws/live, REST API at :8001
  provides:
    - Next.js 14 Pages Router scaffold with Bootstrap 5 dark theme
    - JWT auth hook (useAuth) with first-run setup flow
    - useWebSocket hook with exponential backoff reconnect and status indicator
    - ConnectionsTable component with DOM-mutation delta row injection
    - lib/types.ts, lib/api.ts, lib/countryFlag.ts foundations
    - Jest + React Testing Library setup with 15 RED test stubs
  affects: [frontend scaffold, auth, websocket client, live connections table]
tech_stack:
  added:
    - Next.js 14.2.35 (Pages Router, TypeScript)
    - React 18 + react-dom 18
    - Bootstrap 5.3.8 (via npm, dark theme via data-bs-theme)
    - Recharts 2.15.4 (installed, used in 06-02/06-03)
    - Jest 30 + @testing-library/react + jest-environment-jsdom
  patterns:
    - DOM-mutation delta injection (no JSX re-render for live table rows)
    - Exponential backoff WebSocket reconnect (1s base, 2x per attempt, 30s max)
    - Pause/resume pattern with isPausedRef + pausedBufferRef (cap 500)
    - ESM-compatible jest.config.ts using next/jest.js
key_files:
  created:
    - frontend/ (Next.js 14 scaffold)
    - frontend/pages/_app.tsx
    - frontend/pages/_document.tsx
    - frontend/pages/index.tsx
    - frontend/styles/globals.css
    - frontend/lib/types.ts
    - frontend/lib/api.ts
    - frontend/lib/countryFlag.ts
    - frontend/hooks/useAuth.ts
    - frontend/hooks/useWebSocket.ts
    - frontend/components/LoginPage.tsx
    - frontend/components/WsStatusIndicator.tsx
    - frontend/components/ConnectionsTable.tsx
    - frontend/next.config.mjs (updated with proxy rewrites)
    - frontend/jest.config.ts
    - frontend/jest.setup.ts
    - frontend/hooks/__tests__/useAuth.test.ts
    - frontend/hooks/__tests__/useWebSocket.test.ts
    - frontend/components/__tests__/ConnectionsTable.test.tsx
  modified: []
decisions:
  - "next.config.mjs retained as ESM (not converted to .js CJS) — rewrites work identically"
  - "jest.config.ts uses next/jest.js (with .js extension) for ESM compatibility with Jest 30"
  - "ConnectionsTable uses prop-driven useEffect injection pattern rather than imperative handle"
  - "Pause buffer capped at 500 events to prevent unbounded memory growth during pause"
  - "WS URL uses ws:// (not wss://) as backend is local-only at 127.0.0.1:8001"
metrics:
  duration_seconds: 1281
  completed_date: "2026-04-06"
  tasks_completed: 8
  files_created: 19
---

# Phase 6 Plan 01: App Scaffold, Auth Flow, WebSocket Client, Live Connections Table Summary

**One-liner:** Next.js 14 Pages Router scaffold with Bootstrap 5 dark theme, JWT login/setup flow, exponential-backoff WebSocket hook, and DOM-mutation delta-injection live connections table.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1-A | Next.js 14 scaffold | 0a109f2 | frontend/ (12 files) |
| 0-A | Jest + RTL setup | a38e073 | jest.config.ts, jest.setup.ts |
| 0-B | Test stubs (15 RED) | a38e073 | hooks/__tests__/, components/__tests__/ |
| 1-B | Dark theme and globals | e8f5593 | _document.tsx, _app.tsx, globals.css |
| 1-C | Types, API client, rewrites | e8f5593 | lib/types.ts, lib/api.ts, lib/countryFlag.ts, next.config.mjs |
| 2-A | useAuth hook | 218f30f | hooks/useAuth.ts |
| 2-B | LoginPage component | 218f30f | components/LoginPage.tsx |
| 3-A | useWebSocket + WsStatusIndicator | 0a53d25 | hooks/useWebSocket.ts, components/WsStatusIndicator.tsx |
| 4-A | ConnectionsTable | bfbe53f | components/ConnectionsTable.tsx |
| 5-A | Dashboard page assembly | 63c3292 | pages/index.tsx |

## Verification Results

- `npx tsc --noEmit`: PASSED (0 errors)
- `npm run build`: PASSED (✓ Compiled successfully, 3/3 static pages)
- `npm test -- --passWithNoTests`: PASSED (3 suites, 15 todo, 0 failures)
- `npm run lint`: Not run separately (integrated in build, passed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed Jest ESM import for next/jest**
- **Found during:** Task 0-A
- **Issue:** Jest 30 requires `import nextJest from 'next/jest.js'` (with `.js` extension) when running in ESM context; `'next/jest'` throws ERR_MODULE_NOT_FOUND
- **Fix:** Changed import to `next/jest.js` in jest.config.ts
- **Files modified:** frontend/jest.config.ts
- **Commit:** a38e073

**2. [Rule 2 - ESLint] Added eslint-disable for unused imports in test stubs**
- **Found during:** Task 5-A build
- **Issue:** `npm run build` runs ESLint and failed on `'render'` and `'renderHook'` defined but never used in stub files
- **Fix:** Added `// eslint-disable-next-line @typescript-eslint/no-unused-vars` comments on stub imports
- **Files modified:** components/__tests__/ConnectionsTable.test.tsx, hooks/__tests__/useAuth.test.ts, hooks/__tests__/useWebSocket.test.ts
- **Commit:** 63c3292

**3. [Rule 2 - CLAUDE.md] next.config.mjs retained as ESM format**
- **Found during:** Task 1-C
- **Issue:** Plan specifies creating `next.config.js` with `module.exports`, but scaffold created `next.config.mjs` with `export default`
- **Fix:** Updated `next.config.mjs` with rewrites in ESM format (functionally identical). No file rename needed as Next.js 14 supports both.
- **Files modified:** frontend/next.config.mjs

## Known Stubs

None — all components are fully implemented with real data wiring.

## Self-Check: PASSED

All 19 files verified present. All 8 task commits verified in git log.
