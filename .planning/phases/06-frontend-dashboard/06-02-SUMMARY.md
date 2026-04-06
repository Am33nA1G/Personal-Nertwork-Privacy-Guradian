---
phase: 06-frontend-dashboard
plan: 02
subsystem: alerts-panel
tags: [react, alerts, suppress, resolve, pause-resume, error-states, suppressions-log]
dependency_graph:
  requires:
    - phase-06-plan-01: Next.js scaffold, useWebSocket, useAuth, ConnectionsTable, lib/api.ts, lib/types.ts
  provides:
    - AlertsPanel component with severity color-coded cards and Suppress/Resolve actions
    - Pause/Resume wired into useWebSocket hook with pending buffer and count
    - SuppressionsLog component with Undo action (SUPP-04)
    - Error/loading/empty states for all async operations
    - Split dashboard layout: col-4 alerts + col-8 connections
  affects: [alerts panel, suppression log, dashboard layout, useWebSocket hook, pause behavior]
tech_stack:
  added:
    - "@testing-library/dom 10.x (peer dep for @testing-library/react, was missing)"
  patterns:
    - "Alert state owned by index.tsx (fetch + WS append), AlertsPanel is display-only"
    - "Pause/resume encapsulated in useWebSocket hook (isPausedRef + pendingRef)"
    - "Immutable state updates throughout (spread/filter, no mutation)"
    - "Per-item action state map for spinner/error isolation"
key_files:
  created:
    - frontend/components/AlertsPanel.tsx
    - frontend/components/SuppressionsLog.tsx
    - frontend/components/__tests__/AlertsPanel.test.tsx
    - frontend/components/__tests__/SuppressionsLog.test.tsx
  modified:
    - frontend/hooks/useWebSocket.ts (pause/resume, pendingCount, isPaused returned)
    - frontend/pages/index.tsx (AlertsPanel wired, split layout, alerts state management)
    - frontend/hooks/__tests__/useWebSocket.test.ts (4 pause/resume todo stubs)
    - frontend/package.json (added @testing-library/dom)
decisions:
  - "AlertsPanel is display-only — index.tsx owns alerts state; two sources: initial GET + WS batch appends"
  - "Pause/resume moved fully into useWebSocket hook, not index.tsx refs — cleaner separation of concerns"
  - "useWebSocket merges buffered payloads into single batch call on resume (flatMap over pending array)"
  - "pendingCount calculated from payload item counts (connections + alerts) for accurate banner display"
  - "SuppressionsLog renders in-component for 06-02; placement in tab/page finalized in 06-03"
metrics:
  duration_seconds: 681
  completed_date: "2026-04-06"
  tasks_completed: 9
  files_created: 4
  files_modified: 4
---

# Phase 6 Plan 02: Alerts Panel, Suppress/Resolve, Pause/Resume, Error/Loading States Summary

**One-liner:** Severity color-coded AlertsPanel with suppress/resolve actions, pause/resume fully encapsulated in useWebSocket hook with buffer flush, SuppressionsLog with undo action, and complete loading/error/empty states for all async operations.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 0-A | AlertsPanel test stubs | 513d398 | components/__tests__/AlertsPanel.test.tsx |
| 0-B | SuppressionsLog test stubs | 513d398 | components/__tests__/SuppressionsLog.test.tsx |
| 0-C | Pause/resume test stubs | 513d398 | hooks/__tests__/useWebSocket.test.ts |
| 1-A | AlertsPanel component | 96dc457 | components/AlertsPanel.tsx |
| 1-B | Wire AlertsPanel into index.tsx | 96dc457 | pages/index.tsx |
| 2-A | Pause/Resume in useWebSocket | a3b5436 | hooks/useWebSocket.ts, pages/index.tsx |
| 3-A | SuppressionsLog component | e79e35c | components/SuppressionsLog.tsx |
| Wave 4 | Error/loading state audit | — | (verified inline, no separate commit) |

## Verification Results

- `npx tsc --noEmit`: PASSED (0 errors)
- `npm run build`: PASSED (✓ Compiled, 3/3 static pages, 90.5 kB bundle)
- `npm test -- --passWithNoTests`: PASSED (5 suites, 31 todo, 0 failures)
- `npm run lint`: PASSED (no ESLint warnings or errors)

## Error/Loading State Audit

| Component | Loading | Error | Empty |
|-----------|---------|-------|-------|
| AlertsPanel (initial data) | Skeleton cards + visually-hidden sr text | `alert-danger` with message (from parent prop) | "No active alerts" centered muted |
| AlertsPanel (action) | Spinner in both buttons + disabled | Inline `text-danger` badge beside buttons | N/A |
| SuppressionsLog | Skeleton rows + sr text | `alert-danger` with Retry button | "No suppressions on record" centered muted |
| WS disconnected | N/A | Navbar indicator (WsStatusIndicator) | N/A |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing @testing-library/dom peer dependency**
- **Found during:** Task 1-A (Wave 1 TypeScript check)
- **Issue:** `@testing-library/react@16.3.2` requires `@testing-library/dom` as peer dep; it was absent, causing tsc to report `screen`, `fireEvent`, `waitFor` as missing exports
- **Fix:** `npm install @testing-library/dom --save-dev` in frontend/
- **Files modified:** frontend/package.json, frontend/package-lock.json
- **Commit:** 96dc457

**2. [Rule 3 - Blocking] Removed forward-reference import in SuppressionsLog test stub**
- **Found during:** Task 0-B (tsc check before SuppressionsLog existed)
- **Issue:** Importing `../SuppressionsLog` before the file was created caused TS2307 error breaking the build
- **Fix:** Removed the import from the stub (stubs only use `it.todo`, no component needed); re-added once component was created in Wave 3
- **Files modified:** frontend/components/__tests__/SuppressionsLog.test.tsx
- **Commit:** 96dc457

**3. [Rule 1 - Design] Pause/Resume moved from index.tsx refs to useWebSocket hook**
- **Found during:** Task 2-A
- **Issue:** Plan 02 Task 2-A specifies adding pause/resume to the hook, but the existing index.tsx already had inline `isPausedRef`/`pausedBufferRef` logic from 06-01. Moving to the hook removes duplication and provides a cleaner API.
- **Fix:** useWebSocket now returns `{ isPaused, pendingCount, pause, resume }`. index.tsx simplified to call `pause()`/`resume()` from the hook.
- **Files modified:** hooks/useWebSocket.ts, pages/index.tsx
- **Commit:** a3b5436

## Known Stubs

None — all components are fully implemented with real data wiring.

SuppressionsLog placement (tab vs. dedicated page) is deferred to 06-03 per plan. The component is complete and ready to embed.

## Self-Check: PASSED
