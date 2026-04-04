---
phase: 01-capture-foundation
plan: "01"
subsystem: infra
tags: [python, scapy, npcap, fastapi, pyyaml, pytest, pytest-asyncio, windows, ctypes, winreg]

# Dependency graph
requires: []
provides:
  - pnpg Python package skeleton (pnpg/__init__.py)
  - Config loader with defaults and YAML merge (pnpg/config.py)
  - Npcap and admin privilege startup gate (pnpg/prereqs.py)
  - Documented default config.yaml with all runtime thresholds
  - Pinned requirements.txt with 7 dependencies
  - pytest infrastructure with asyncio_mode=auto
  - 8 passing unit tests covering CAP-02, CAP-03, CONFIG-01, CONFIG-02
affects: [01-02, 01-03, all subsequent plans in phase 01]

# Tech tracking
tech-stack:
  added:
    - scapy>=2.7.0 (packet capture — used in 01-02)
    - fastapi>=0.115.0 (API layer — used in phase 03+)
    - uvicorn[standard]>=0.32.0 (ASGI server — used in phase 03+)
    - psutil>=6.0.0 (process mapping — used in 01-02)
    - pyyaml>=6.0.0 (config.yaml parsing — used here)
    - pytest>=8.0.0 + pytest-asyncio>=1.3.0 (test framework — used throughout)
  patterns:
    - TDD RED→GREEN: test stubs first, implementation second, commit each phase separately
    - Config merge: DEFAULT_CONFIG as source of truth; load_config() returns new dict, never mutates defaults
    - Cold-start gate: check_npcap() then check_admin() — both sys.exit(1) on failure before any network activity
    - Immutable config: dict(DEFAULT_CONFIG) copy ensures downstream cannot mutate defaults

key-files:
  created:
    - requirements.txt
    - pytest.ini
    - config.yaml
    - pnpg/__init__.py
    - pnpg/config.py
    - pnpg/prereqs.py
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_prereqs.py
    - tests/test_config.py
    - .gitignore
  modified: []

key-decisions:
  - "Npcap detection uses filesystem check first (System32/Npcap dir), then winreg as fallback — matches Scapy's own detection approach"
  - "load_config() returns dict(DEFAULT_CONFIG) copy on any error — never mutates DEFAULT_CONFIG (immutability pattern)"
  - "Unknown YAML keys trigger logging.warning() and are silently dropped — allows forward-compat config files without crashing"
  - "Invalid YAML logs warning with 'parse error' text and returns ALL defaults immediately — no partial merge"

patterns-established:
  - "Pattern 1 (Startup gate): load_config() → check_npcap() → check_admin() — must always run in this order before any sniffing"
  - "Pattern 2 (Config immutability): dict(DEFAULT_CONFIG) copy at top of load_config(); user overrides applied to copy, not to DEFAULT_CONFIG"
  - "Pattern 3 (sys.exit on prereq failure): check_* functions print error to stderr, then sys.exit(1) — no exceptions raised, just hard exit"
  - "Pattern 4 (TDD commit discipline): test commit (RED) then implementation commit (GREEN) — separate commits per phase"

requirements-completed: [CAP-02, CAP-03, CONFIG-01, CONFIG-02, CONFIG-03, SYS-01]

# Metrics
duration: 15min
completed: 2026-04-01
---

# Phase 01 Plan 01: Project Skeleton, Config Loader, and Startup Prerequisites Summary

**Cold-start gate with Npcap/admin validation via ctypes+winreg, PyYAML config loader with 12-key DEFAULT_CONFIG and graceful fallback, and 8-test pytest suite covering CAP-02, CAP-03, CONFIG-01, CONFIG-02**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-01T01:27:32Z
- **Completed:** 2026-04-01T01:42:00Z
- **Tasks:** 2 (Task 1: RED stubs; Task 2: GREEN implementation)
- **Files modified:** 11 created, 0 modified

## Accomplishments

- Established the full cold-start gate: config loads before any sniffing, Npcap is verified, admin privileges are confirmed — all with clear error messages and sys.exit(1) on failure
- Config loader (pnpg/config.py) handles missing file, invalid YAML, and unknown keys gracefully with logging, never crashes startup
- Full test infrastructure in place: pytest 9.0.2, pytest-asyncio 1.3.0, asyncio_mode=auto, 8 passing tests, all fixtures (mock_npcap_missing, mock_npcap_present, mock_admin, mock_not_admin) wired correctly

## Task Commits

Each task was committed atomically:

1. **Task 1: Project skeleton, dependencies, test infrastructure, and Wave 0 test stubs** - `89d2400` (test)
2. **Task 2: Implement prereqs.py, config.py, config.yaml — make all tests GREEN** - `62fd5fc` (feat)
3. **Deviation: Add .gitignore (Rule 2 — missing critical)** - `2d38762` (chore)

_Note: TDD tasks have two commits each (test RED → feat GREEN)_

## Files Created/Modified

- `requirements.txt` — 7 pinned dependencies (scapy, fastapi, uvicorn, psutil, pyyaml, pytest, pytest-asyncio)
- `pytest.ini` — pytest config with asyncio_mode=auto and testpaths=tests
- `config.yaml` — all 12 runtime thresholds documented as commented-out defaults
- `pnpg/__init__.py` — package stub
- `pnpg/config.py` — DEFAULT_CONFIG dict (12 keys), load_config() with YAML merge and graceful error handling
- `pnpg/prereqs.py` — check_npcap() (filesystem + registry detection), check_admin() (ctypes IsUserAnAdmin)
- `tests/__init__.py` — package stub
- `tests/conftest.py` — shared fixtures: mock_npcap_missing, mock_npcap_present, mock_admin, mock_not_admin, tmp_config_path
- `tests/test_prereqs.py` — 4 tests: npcap exits/passes, admin exits/passes
- `tests/test_config.py` — 4 tests: defaults, override, unknown key ignored, invalid YAML
- `.gitignore` — Python, pytest, venv, OS, IDE artifacts

## Decisions Made

- Used filesystem check as primary Npcap detection (`System32\Npcap` dir), winreg as fallback. Rationale: matches Scapy's own detection, avoids dependency on registry-only installs.
- `load_config()` returns `dict(DEFAULT_CONFIG)` (shallow copy) on ALL error paths. Rationale: downstream code must never be able to mutate DEFAULT_CONFIG by modifying the returned dict.
- Invalid YAML (parse error) returns all defaults immediately without partial merge. Rationale: a partially corrupt config is worse than all-defaults since it may produce inconsistent state.
- Added `.gitignore` as deviation Rule 2 (missing critical setup) — without it, `__pycache__` and `.pytest_cache` would pollute the repo on first test run.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added .gitignore for Python artifacts**
- **Found during:** Task 2 (after running tests and noticing untracked pycache directories)
- **Issue:** No .gitignore existed; `__pycache__/`, `.pytest_cache/`, and `*.pyc` files would be committed to git on next `git add .`
- **Fix:** Created `.gitignore` with standard Python/pytest/venv/OS/IDE entries
- **Files modified:** `.gitignore` (created)
- **Verification:** `git status --short` no longer shows pycache directories
- **Committed in:** `2d38762` (separate chore commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential for repo hygiene. No scope creep — standard Python project requirement.

## Issues Encountered

None — plan executed cleanly. The `mock_npcap_missing` fixture required careful patching of both `os.path.isdir` (returning False) and `winreg.OpenKey` (raising FileNotFoundError) to correctly simulate the two-strategy Npcap detection in `check_npcap()`. Both fixtures were wired correctly on first attempt.

## User Setup Required

**External prerequisite requires manual installation.**

Before running the full application (not required for the tests in this plan):

- **Npcap**: Install from https://npcap.com — download the installer and enable "WinPcap API-compatible mode" during installation. Required for Scapy packet capture on Windows. Without it, `check_npcap()` will exit with code 1.
- **Administrator terminal**: Run the application from an elevated terminal (right-click → Run as administrator). Required for raw socket access. Without it, `check_admin()` will exit with code 1.

The tests in this plan mock both prerequisites and pass without Npcap or admin elevation.

## Known Stubs

None — all code in this plan is fully implemented with no stub values that flow to rendering.

## Next Phase Readiness

- Config and prereqs are production-ready; plan 01-02 (sniffer + queue bridge) can import and call both immediately
- `DEFAULT_CONFIG["queue_size"]` (500), `DEFAULT_CONFIG["interface"]` (None), and `DEFAULT_CONFIG["poll_interval_ms"]` (200) are ready for plan 01-02 consumption
- Test fixtures in conftest.py are shared infrastructure — plans 01-02 and 01-03 add their own fixtures to conftest.py

## Self-Check: PASSED

All 12 created files verified present on disk. All 3 task commits (89d2400, 62fd5fc, 2d38762) verified in git log. Final metadata commit df7c4f8 confirmed.

---
*Phase: 01-capture-foundation*
*Completed: 2026-04-01*
