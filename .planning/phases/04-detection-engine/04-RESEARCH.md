# Phase 4: Detection Engine - Research

**Researched:** 2026-04-05
**Domain:** Rule-based anomaly detection, in-memory rate limiting, allowlist/suppression logic, alert object construction, Python asyncio pipeline integration
**Confidence:** HIGH (all patterns drawn from existing codebase conventions plus well-known Python stdlib primitives; no new external dependencies required)

---

## Summary

Phase 4 sits immediately after Phase 3 in the pipeline. By the time an event reaches the detection engine, it carries: `dst_ip`, `dst_hostname`, `dst_port`, `protocol`, `process_name`, `pid`, `dst_country`, `dst_asn`, `dst_org`, and `threat_intel.is_blocklisted`. The detection engine evaluates 10 named rules (DET-01 through DET-10) against this enriched event, checks an in-memory allowlist before emitting any alert, applies per-rule per-process rate limiting to suppress alert floods, and returns zero or more structured alert dicts with all required fields (DET-10).

No new Python packages are needed. All state is in-process (Python dicts and sets). The Phase 5 PostgreSQL layer will persist these alerts later; in Phase 4 alerts are returned as a list and held in a bounded buffer in app state. Allowlist and suppression rules are in-memory stores in Phase 4 — API CRUD and PostgreSQL persistence come in Phase 5.

The detection engine must be a pure async function `detect_event(event, config, state) -> list[dict]` that fits into the existing `pipeline_worker.py` stub on line 73 (`# Phase 4: alerts = detection_engine(event, config)`). It returns a list of alert dicts (empty list if no rules fire or all alerts are suppressed or allowlisted).

**Primary recommendation:** Build `pnpg/pipeline/detector.py` containing all rule functions, the rate limiter, allowlist checker, and alert object factory. Introduce a `DetectorState` dataclass (in the same file or a companion `detector_state.py`) that holds all inter-event mutable state. Wire into `pipeline_worker.py` with a single `await detect_event(event, config, detector_state)` call. Update `main.py` lifespan to create `DetectorState`, load the TOR exit list, and pass state to the worker.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DET-01 | Flag connections with no resolvable domain as WARNING | `event["dst_hostname"] == event["dst_ip"]` means DNS failed; emit severity="WARNING", rule_id="DET-01" |
| DET-02 | Flag a process exceeding 100 connections/min as HIGH severity (rate spike) | Rolling 60-second sliding window counter per process; threshold from new config key `connection_rate_threshold_per_min: 100` |
| DET-03 | Flag connections on unusual ports from unknown process OR at abnormal frequency (compound rule, reduces false positives) | `dst_port NOT IN port_allowlist AND (process_name == "unknown process" OR rate_spike)` — success criterion 3 explicitly requires false-positive gate |
| DET-04 | Flag connections from "unknown process" as ALERT severity | `event["process_name"] == "unknown process"` — exact string sentinel used by `process_mapper.py` |
| DET-05 | Flag connections to blocklisted IP or domain as CRITICAL | `event["threat_intel"]["is_blocklisted"]` is `True` — already set by `check_threat_intel()` in Phase 3 |
| DET-06 | Flag connections to TOR exit nodes as HIGH | Separate local TOR exit node IP list (plain text); loaded into `frozenset` at startup; same pattern as blocklist |
| DET-07 | Flag first-ever external destination for a process as LOW (discovery) | In-memory `dict[str, set[str]]` mapping process key to set of seen dst_ips; alert on first appearance |
| DET-08 | All thresholds are named constants from `config.yaml` — no magic numbers | All literals come from `config` dict; add new keys: `connection_rate_threshold_per_min`, `tor_exit_list_path` |
| DET-09 | Rate-limit alerts to max 1 per rule per process per second | `dict[(rule_id, process_name), float]` storing last-emit monotonic time; suppress if `monotonic() - last < alert_rate_limit_per_sec` |
| DET-10 | All alerts include: alert_id, timestamp, severity, rule_id, reason, confidence, process_name, pid, dst_ip, dst_hostname, recommended_action, suppressed | Alert factory function `_make_alert()` producing immutable dict with all 12 fields; `alert_id = str(uuid.uuid4())` |
| ALLOW-01 | User can create allowlist rule scoped to process + destination (IP or domain) | In-memory list of rule dicts: `{process_name, dst_ip, dst_hostname, expires_at}` |
| ALLOW-02 | User can create global allowlist rule for a destination (all processes) | Same structure with `process_name=None` meaning "any process" |
| ALLOW-03 | Allowlist rules can have optional expiry timestamp (null = permanent) | Check `rule["expires_at"] is None or datetime.now(UTC) < rule["expires_at"]`; use timezone-aware datetime |
| ALLOW-04 | Detection engine checks allowlist before emitting alert — matching rules suppress | `_is_allowlisted(event, state)` called before constructing alert object; allowlisted events produce no alert |
| SUPP-01 | User can suppress a single alert instance ("dismiss this one") | In-memory `set[str]` of suppressed `alert_id` strings; populated externally (Phase 5 API); checked in `detect_event()` |
| SUPP-02 | User can suppress all future alerts from a specific rule for a specific process | In-memory `set[tuple]` of `(rule_id, process_name)` suppression tuples; alert with `suppressed=True` is still appended to output list but marked |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

- **No framework substitutions**: Python 3.11+, FastAPI — no new frameworks, ORMs, or libraries
- **Local only**: Detection uses only local data (no external calls); TOR exit list downloaded once and used as a local file
- **Immutability**: Every enrichment stage returns a new dict — detection follows the same pattern; alert objects are immutable dicts constructed by `_make_alert()`
- **File size**: 200-400 lines typical, 800 max — split `detector.py` if it exceeds this
- **Config**: All thresholds from `config.yaml` via `DEFAULT_CONFIG`; no magic numbers (DET-08 is an explicit requirement)
- **Error handling**: NEVER silently swallow errors; detection errors must not crash the pipeline (SYS-01/CONFIG-03 in `worker.py` already provide outer protection, but detection internals must also log and continue)
- **Existing config keys to reuse**: `port_allowlist` (DET-03), `alert_rate_limit_per_sec` (DET-09 — already `1`)
- **Existing "unknown process" sentinel**: `process_mapper.py` uses the exact string `"unknown process"` — DET-04 must match this exact string
- **PostgreSQL not in scope for Phase 4**: Alerts returned as `list[dict]`; storage comes in Phase 5
- **Pre-existing pipeline stub**: `worker.py` line 73: `# Phase 4: alerts = detection_engine(event, config)` — this is the exact insertion point

---

## Standard Stack

### Core (all stdlib — no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `uuid` (stdlib) | Python 3.11 built-in | `uuid.uuid4()` for `alert_id` generation | Required by DET-10; zero dependency |
| `time` (stdlib) | Python 3.11 built-in | `time.monotonic()` for rate limiter timestamps | Already used in `dns_resolver.py` and `process_mapper.py` |
| `datetime` (stdlib) | Python 3.11 built-in | `datetime.now(timezone.utc)` for alert timestamps and allowlist expiry | Required for ALLOW-03 and DET-10 |
| `collections.defaultdict` (stdlib) | Python 3.11 built-in | Per-process connection timestamps for DET-02 sliding window | Avoids KeyError on first access |
| `dataclasses` (stdlib) | Python 3.11 built-in | `@dataclass` for `DetectorState` container | Cleaner than plain dict; same convention as Python 3.11 projects |
| `frozenset` (stdlib) | Python 3.11 built-in | TOR exit node IP set; O(1) membership check | Same pattern as `threat_intel.py` blocklist |
| `asyncio` (stdlib) | Python 3.11 built-in | `async def detect_event()` entrypoint; preserves Phase 5 upgrade path | Already the core async runtime |

### Supporting (already in requirements.txt)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pyyaml` | 6.0.0+ | Already used for `config.py` — no setup needed | New config keys in `config.yaml` and `DEFAULT_CONFIG` |
| `pytest` / `pytest-asyncio` | 8.0+ / 0.23+ | Test framework already configured | All detection rule tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-memory `dict` rate limiter | Redis rate limiting | Redis not available until Phase 7; in-memory is correct for Phase 4 |
| Plain `frozenset` for TOR list | External Tor Project API at runtime | External API = network call; CLAUDE.md forbids runtime external calls |
| `list[float]` sliding window | Time-bucketed counters | List + evict-on-read is simpler and correct for bounded process count |
| In-memory allowlist | SQLAlchemy + PostgreSQL | Database comes in Phase 5; in-memory is Phase 4 scope |

**Installation:** No new packages needed.

```bash
# No pip install required for Phase 4.
# TOR exit node list — download once at setup time:
# curl -o data/tor-exit-nodes.txt https://check.torproject.org/torbulkexitlist
# Or commit a static snapshot to the repo under data/
```

---

## Architecture Patterns

### Recommended Module Structure
```
pnpg/pipeline/
├── detector.py          # All detection logic: rules, rate limiter, allowlist check, alert factory, detect_event()
├── worker.py            # Modified: add detector_state param; call detect_event() after Phase 3 enrichment
pnpg/
├── config.py            # Modified: add connection_rate_threshold_per_min, tor_exit_list_path to DEFAULT_CONFIG
├── main.py              # Modified: create DetectorState in lifespan, load TOR list, pass state to worker
config.yaml              # Modified: document new Phase 4 config keys
tests/test_pipeline/
├── test_detector.py     # New: one test per rule + rate limiter + allowlist + alert factory
```

If `detector.py` is projected to exceed 400 lines, split into:
- `detector_rules.py` — the 7 rule functions (DET-01 to DET-07)
- `detector.py` — `DetectorState`, rate limiter, allowlist checker, `_make_alert()`, `detect_event()`

### Pattern 1: DetectorState — Shared Mutable State Passed as Parameter
**What:** A single dataclass created in lifespan and passed to `detect_event()` on every call. Contains all cross-event mutable state.

**When to use:** Always — never module-level globals (they break test isolation; same reasoning as `process_cache` in Phase 2).

```python
# Source: project convention established by process_mapper.py (process_cache dict passed as param)
from dataclasses import dataclass, field

@dataclass
class DetectorState:
    # DET-02: per-process connection timestamps for sliding window
    connection_timestamps: dict = field(default_factory=dict)  # {process_key: list[float]}

    # DET-07: per-process seen destination IPs
    first_seen: dict = field(default_factory=dict)  # {process_key: set[str]}

    # DET-09: per-rule per-process last-emit monotonic timestamp
    rate_limiter: dict = field(default_factory=dict)  # {(rule_id, process_key): float}

    # DET-06: TOR exit node IPs (loaded at startup)
    tor_exit_nodes: frozenset = field(default_factory=frozenset)

    # ALLOW-01/02/03/04: in-memory allowlist rules
    allowlist: list = field(default_factory=list)  # list[dict]

    # SUPP-01: suppressed specific alert_ids
    suppressed_alert_ids: set = field(default_factory=set)  # set[str]

    # SUPP-02: suppressed (rule_id, process_name) combinations
    suppressed_rules: set = field(default_factory=set)  # set[tuple[str, str | None]]
```

### Pattern 2: Rule Function Signature
**What:** Each rule is a standalone function taking `(event, config, state) -> dict | None`. Returns an alert dict if the rule fires, `None` otherwise. The `detect_event()` loop calls each in sequence.

```python
# Source: project convention — single-responsibility functions, no side effects on event
def rule_det01_unknown_domain(
    event: dict, config: dict, state: DetectorState
) -> dict | None:
    """DET-01: No resolvable domain (dst_hostname == dst_ip means DNS failed)."""
    dst_ip = event.get("dst_ip", "")
    dst_hostname = event.get("dst_hostname", "")
    if not dst_ip or (dst_hostname and dst_hostname != dst_ip):
        return None  # DNS resolved successfully
    return _make_alert(
        event=event,
        rule_id="DET-01",
        severity="WARNING",
        reason=f"No reverse DNS record for {dst_ip}",
        confidence=0.5,
        recommended_action="MONITOR",
    )
```

### Pattern 3: Alert Factory (_make_alert)
**What:** Single function that constructs all 12 DET-10 fields. Called by every rule function. All fields are always present — no optional keys that callers might forget.

```python
# Source: REQUIREMENTS.md "Alert Object (Production Schema)"
import uuid
from datetime import datetime, timezone

def _make_alert(
    event: dict,
    rule_id: str,
    severity: str,
    reason: str,
    confidence: float,
    recommended_action: str,
    suppressed: bool = False,
) -> dict:
    return {
        "alert_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": severity,
        "rule_id": rule_id,
        "reason": reason,
        "confidence": confidence,
        "process_name": event.get("process_name", "unknown process"),
        "pid": event.get("pid", -1),
        "dst_ip": event.get("dst_ip", ""),
        "dst_hostname": event.get("dst_hostname", ""),
        "recommended_action": recommended_action,
        "suppressed": suppressed,
    }
```

### Pattern 4: Per-Rule Per-Process Rate Limiter (DET-09)
**What:** Before appending an alert to the output list, check if the same `(rule_id, process_name)` fired within `alert_rate_limit_per_sec` seconds. If yes, silently drop. If no, record the timestamp and allow.

```python
# Source: time.monotonic() pattern from dns_resolver.py (TtlLruCache) and process_mapper.py
def _is_rate_limited(
    rule_id: str,
    process_name: str,
    state: DetectorState,
    config: dict,
) -> bool:
    key = (rule_id, process_name)
    last_emit = state.rate_limiter.get(key, 0.0)
    min_interval = config.get("alert_rate_limit_per_sec", 1)
    now = time.monotonic()
    if now - last_emit < min_interval:
        return True  # Suppress
    state.rate_limiter[key] = now  # Update ONLY when not suppressed
    return False
```

**Critical ordering:** Update `rate_limiter[key]` only when the alert IS emitted, not when it is suppressed. Updating on suppression would permanently starve all future alerts.

### Pattern 5: Allowlist Pre-Check (ALLOW-04)
**What:** Before calling `_make_alert()`, check if the event matches any active allowlist rule. If it matches, return `None` from the rule function immediately — no alert is constructed.

```python
# Source: REQUIREMENTS.md ALLOW-01 through ALLOW-04
from datetime import datetime, timezone

def _is_allowlisted(event: dict, state: DetectorState) -> bool:
    dst_ip = event.get("dst_ip", "")
    dst_hostname = event.get("dst_hostname", "")
    process_name = event.get("process_name", "")
    now = datetime.now(timezone.utc)

    for rule in state.allowlist:
        # ALLOW-03: check expiry
        expires_at = rule.get("expires_at")
        if expires_at is not None and now > expires_at:
            continue  # Expired rule

        # ALLOW-01 / ALLOW-02: check process scope (None = any process)
        rule_process = rule.get("process_name")
        if rule_process is not None and rule_process != process_name:
            continue

        # Check destination match (IP or hostname)
        rule_dst = rule.get("dst_ip") or rule.get("dst_hostname")
        if rule_dst and rule_dst in (dst_ip, dst_hostname):
            return True

    return False
```

### Pattern 6: DET-02 Sliding Window Rate Counter
**What:** Maintain a `list[float]` of monotonic timestamps per process key. On each event, append current time, evict entries older than 60 seconds, then count. If count exceeds `connection_rate_threshold_per_min`, fire DET-02.

```python
# Source: standard sliding window pattern (no external library)
def _update_connection_rate(
    process_key: str,
    state: DetectorState,
    config: dict,
) -> int:
    """Returns current connections-per-minute count for the process."""
    now = time.monotonic()
    window_sec = 60.0
    ts_list = state.connection_timestamps.setdefault(process_key, [])
    ts_list.append(now)
    cutoff = now - window_sec
    # Replace list with evicted version — evict on every call to bound memory
    state.connection_timestamps[process_key] = [t for t in ts_list if t >= cutoff]
    return len(state.connection_timestamps[process_key])
```

**Memory note:** At 10,000 events/sec with a single process, the list holds 600,000 timestamps. This is approximately 4.8 MB per process (floats are 8 bytes each). With typical workloads (tens of processes, not thousands), this is acceptable for Phase 4. A Phase 7 optimization can switch to a bucketed counter if memory pressure is observed.

### Pattern 7: DET-07 First-Seen Tracker
**What:** Dict mapping process key to set of seen `dst_ip` strings. Alert on first occurrence only.

```python
# Source: project convention — per-process state dict
def rule_det07_new_destination(
    event: dict, config: dict, state: DetectorState
) -> dict | None:
    process_key = _process_key(event)  # see Pattern 8 below
    dst_ip = event.get("dst_ip", "")
    if not dst_ip:
        return None
    seen = state.first_seen.setdefault(process_key, set())
    if dst_ip in seen:
        return None
    seen.add(dst_ip)
    return _make_alert(
        event=event,
        rule_id="DET-07",
        severity="LOW",
        reason=f"First connection from {event.get('process_name', 'unknown')} to {dst_ip}",
        confidence=0.3,
        recommended_action="MONITOR",
    )
```

### Pattern 8: Process Key Helper
**What:** Resolve the correct dict key for per-process state. For known processes, key on `process_name` (stable). For `"unknown process"`, key on `(process_name, pid)` to avoid merging state from different actual processes that both resolved to the sentinel.

```python
# Source: pitfall analysis — "unknown process" string is a sentinel, not a real name
def _process_key(event: dict) -> str:
    process_name = event.get("process_name", "unknown process")
    if process_name == "unknown process":
        pid = event.get("pid", -1)
        return f"unknown_process_{pid}"
    return process_name
```

### Pattern 9: TOR Exit Node Loader (DET-06)
**What:** Plain-text file, one IPv4 per line. Loaded into `frozenset[str]` at startup. Same pattern as `threat_intel.py`.

```python
# Source: mirrors threat_intel.py load_blocklist() exactly
import logging
import os
import time

logger = logging.getLogger(__name__)

def load_tor_exit_nodes(path: str) -> frozenset:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            ips = {
                line.strip()
                for line in fh
                if line.strip() and not line.startswith("#")
            }
        logger.info("Loaded %d TOR exit node IPs from %s", len(ips), path)
        return frozenset(ips)
    except FileNotFoundError:
        logger.warning("TOR exit node list not found at %s — DET-06 disabled", path)
        return frozenset()
```

### Pattern 10: detect_event() Main Entrypoint
**What:** The async function called from `pipeline_worker.py`. Runs all rules, applies allowlist and rate limiting, returns list of alert dicts (empty if none fired).

```python
# Source: pipeline pattern from enrich_event(), enrich_dns(), enrich_geo(), check_threat_intel()
async def detect_event(
    event: dict,
    config: dict,
    state: DetectorState,
) -> list[dict]:
    """Run all detection rules. Returns list of alert dicts (may be empty). Never raises."""
    _update_connection_rate(_process_key(event), state, config)  # DET-02 state update

    rules = [
        rule_det01_unknown_domain,
        rule_det02_rate_spike,
        rule_det03_unusual_port,
        rule_det04_unknown_process,
        rule_det05_blocklisted,
        rule_det06_tor_exit_node,
        rule_det07_new_destination,
    ]

    alerts = []
    for rule_fn in rules:
        try:
            alert = rule_fn(event, config, state)
        except Exception as exc:
            logger.error(
                "Detection rule %s raised: %s", rule_fn.__name__, exc, exc_info=True
            )
            continue

        if alert is None:
            continue

        rule_id = alert["rule_id"]
        process_name = alert["process_name"]

        # ALLOW-04: allowlist pre-check (before rate limiting — allowlisted events
        # must NOT consume a rate-limit slot)
        if _is_allowlisted(event, state):
            continue

        # SUPP-02: rule+process suppression
        if (rule_id, process_name) in state.suppressed_rules:
            alerts.append({**alert, "suppressed": True})
            continue

        # SUPP-01: individual alert suppression (check after alert_id is known)
        if alert["alert_id"] in state.suppressed_alert_ids:
            alerts.append({**alert, "suppressed": True})
            continue

        # DET-09: rate limiting
        if _is_rate_limited(rule_id, process_name, state, config):
            continue

        alerts.append(alert)

    return alerts
```

### Pattern 11: Worker Integration
**What:** Update `pipeline_worker.py` to accept `detector_state` parameter and call `detect_event()`.

```python
# In pnpg/pipeline/worker.py — replace existing stub comment (line 73)

# Signature change:
async def pipeline_worker(
    queue: asyncio.Queue,
    config: dict,
    process_cache: dict,
    dns_cache: TtlLruCache,
    detector_state: DetectorState,        # NEW
) -> None:

# Inside the processing loop, after Phase 3 enrichment:
    # Phase 4: Detection Engine (DET-01 to DET-10, ALLOW-01..04, SUPP-01..02)
    alerts = await detect_event(event, config, detector_state)
    # Phase 5: storage_writer(event, alerts)
    # Phase 5: websocket_push(event, alerts)
```

### Pattern 12: Lifespan Additions (main.py)
**What:** Create `DetectorState`, load TOR list, pass state to worker. Store on `app.state` for Phase 5 API access.

```python
# In pnpg/main.py lifespan — additions for Phase 4
from pnpg.pipeline.detector import DetectorState, load_tor_exit_nodes

    # Phase 4: Initialize detector state
    detector_state = DetectorState()
    detector_state.tor_exit_nodes = load_tor_exit_nodes(config["tor_exit_list_path"])

    # Pass to worker
    worker_task = asyncio.create_task(
        pipeline_worker(queue, config, process_cache, dns_cache, detector_state),
        name="pipeline-worker",
    )

    app.state.detector_state = detector_state  # Phase 5 API will read allowlist, alerts
```

### Anti-Patterns to Avoid
- **Module-level mutable state in detector.py:** Do not use module-level dicts for rate limiter, first-seen tracker, or allowlist. They break test isolation. Use `DetectorState` passed as parameter.
- **Magic numbers in rule functions:** All numeric thresholds (100 connections/min, port list, confidence values) must come from `config` dict or be constants named in ALL_CAPS at module top.
- **Rate-limiting allowlisted events:** Allowlist check must happen BEFORE rate limiter check. An allowlisted event must not consume a rate-limit slot.
- **DET-03 as a simple port check:** Implementing DET-03 as `port NOT IN allowlist` (without the process + frequency condition) produces immediate false-positive flooding. The spec and success criterion 3 explicitly require the compound guard.
- **Timezone-naive datetime in ALLOW-03:** Always use `datetime.now(timezone.utc)` not `datetime.now()` to avoid TypeError when comparing with timezone-aware `expires_at` values.
- **Reusing `connection_rate_threshold` config key for DET-02:** The existing key is documented as connections/sec and its value is 50. DET-02 requires 100/min. Add `connection_rate_threshold_per_min: 100` as a new key.
- **DET-07 keying on bare "unknown process":** Multiple real processes can appear as "unknown process". Key on `_process_key(event)` which includes the PID for the sentinel case.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Unique alert IDs | Custom ID scheme | `str(uuid.uuid4())` | stdlib; collision-free; DET-10 requires it |
| Sliding rate window | Redis, Celery, bucket counter | `list[float]` + evict-on-read | No deps; correct for bounded process count in Phase 4 |
| TOR IP lookup | External Tor Project API at runtime | Local `frozenset` from file | CLAUDE.md forbids runtime external network calls |
| Timezone handling | Manual UTC offset arithmetic | `datetime.now(timezone.utc)` | stdlib; handles DST, offsets correctly |
| Rule dispatch | Plugin registry, DSL, YAML-driven rules | Plain `list` of function references | 10 fixed rules need no abstraction overhead |
| Alert persistence | Custom file format | Not in Phase 4 — PostgreSQL in Phase 5 | Premature; Phase 5 owns all storage |

**Key insight:** Detection rule engines are tempting to over-engineer with plugin systems, DSLs, and config-driven rule definitions. For 10 fixed rules in a local tool, a list of functions is the correct abstraction. The complexity budget for Phase 4 is the rules themselves, not the dispatch mechanism.

---

## Common Pitfalls

### Pitfall 1: DET-03 False Positive Noise
**What goes wrong:** Implementing DET-03 as `port NOT IN port_allowlist` (without compound conditions) fills the alert panel immediately on startup. Chrome uses QUIC on UDP port 443, NTP uses 123, mDNS uses 5353 — all of which are already in the allowlist. But many other legitimate ports exist.

**Why it happens:** The allowlist is finite; real traffic uses many ports (gaming, VoIP, custom protocols).

**How to avoid:** DET-03 must be compound: `dst_port NOT IN port_allowlist AND (process_name == "unknown process" OR rate_spike)`. Success criterion 3 explicitly requires the false-positive gate: "same port from a known process at normal frequency does not" trigger an alert.

**Warning signs:** Alert panel fills within seconds of startup. DET-03 entries for Chrome, Windows Update, or other known processes.

### Pitfall 2: Rate Limiter Timestamp Update Order
**What goes wrong:** Updating `rate_limiter[key] = now` on suppressed calls instead of only on emitted calls causes the rate limiter to permanently suppress all future alerts from that rule/process combination.

**Why it happens:** Misreading the intent — the timestamp records WHEN THE LAST ALERT WAS EMITTED, not when the rule was last evaluated.

**How to avoid:** The sequence in `_is_rate_limited()` must be: (1) read last emit time, (2) if enough time has passed, update timestamp AND return False. Never update on the suppressed path.

**Warning signs:** Success criterion 8 fails — no more than 1 alert per second is emitted in tests, but in sustained runs, alerts stop appearing entirely after the first emission.

### Pitfall 3: DET-07 State Merging for "unknown process"
**What goes wrong:** Multiple real processes that appear as "unknown process" share the same first-seen set, causing DET-07 to fire only once even when multiple different unattributed processes connect to the same new destination.

**Why it happens:** Keying on `process_name` alone collapses all "unknown process" entries into one set.

**How to avoid:** Use `_process_key(event)` which returns `f"unknown_process_{pid}"` for the sentinel, separating state by PID.

**Warning signs:** DET-07 fires only once for the sentinel process regardless of how many different unattributed connections occur.

### Pitfall 4: Timezone-Naive datetime in ALLOW-03
**What goes wrong:** `TypeError: can't compare offset-naive and offset-aware datetimes` when comparing `datetime.now()` (naive) to an `expires_at` stored as UTC with timezone info.

**Why it happens:** Python datetime objects are naive by default; comparing naive to aware raises TypeError.

**How to avoid:** Always use `datetime.now(timezone.utc)`. Store `expires_at` as UTC when adding allowlist rules.

**Warning signs:** Allowlist stops suppressing alerts silently (exception swallowed by try/except in `detect_event()`).

### Pitfall 5: DET-02 Config Key Unit Mismatch
**What goes wrong:** Reusing `connection_rate_threshold: 50` from DEFAULT_CONFIG for DET-02 instead of adding `connection_rate_threshold_per_min: 100`. The existing key was originally documented as connections/sec trigger (a different unit at a different scale).

**How to avoid:** Add `connection_rate_threshold_per_min: 100` as a new key in `DEFAULT_CONFIG`. DET-02 reads from the new key. The old key (`connection_rate_threshold: 50`) can remain for backward compatibility — nothing in Phase 3 or earlier reads it.

**Warning signs:** DET-02 fires at 50 connections/minute instead of 100, or incorrectly fires at 50 events total instead of per-minute.

### Pitfall 6: DET-01 Firing on Private/Loopback IPs
**What goes wrong:** Private IP addresses (10.x.x.x, 192.168.x.x, 172.16.x.x, 127.x.x.x) often have no PTR record. DET-01 fires constantly for LAN traffic.

**How to avoid:** In `rule_det01_unknown_domain`, skip private/loopback IPs. Use `ipaddress.ip_address(dst_ip).is_private` (stdlib). Private-IP DNS failures are expected and not suspicious.

**Warning signs:** Alert panel flooded with DET-01 entries for 192.168.x.x or 10.x.x.x destinations immediately on startup.

### Pitfall 7: detect_event() Declared sync Instead of async
**What goes wrong:** Declaring `detect_event()` as `def` instead of `async def` means Phase 5 cannot add `await` calls inside it (for PostgreSQL allowlist lookups) without breaking the calling contract.

**How to avoid:** Declare `async def detect_event()` from the start. The current Phase 4 implementation has no `await` calls inside, but the `async def` declaration costs nothing and preserves the Phase 5 upgrade path.

**Warning signs:** Phase 5 requires refactoring `detect_event()` to `async def` and updating all call sites, which risks introducing regressions.

---

## Code Examples

### Alert Object — Complete (all 12 DET-10 fields)
```python
# Source: REQUIREMENTS.md "Alert Object (Production Schema)"
{
    "alert_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "timestamp": "2026-04-05T12:00:00+00:00",
    "severity": "HIGH",
    "rule_id": "DET-02",
    "reason": "chrome.exe exceeded 100 connections/min (observed: 134)",
    "confidence": 0.91,
    "process_name": "chrome.exe",
    "pid": 4821,
    "dst_ip": "93.184.216.34",
    "dst_hostname": "example.com",
    "recommended_action": "REVIEW",
    "suppressed": False,
}
```

### Severity and Confidence Scale
| Rule | Severity | Confidence | recommended_action |
|------|----------|------------|--------------------|
| DET-01 unknown domain | WARNING | 0.5 | MONITOR |
| DET-02 rate spike | HIGH | 0.9 | REVIEW |
| DET-03 unusual port + unknown process | ALERT | 0.7 | REVIEW |
| DET-04 unknown process | ALERT | 0.6 | REVIEW |
| DET-05 blocklisted destination | CRITICAL | 1.0 | BLOCK |
| DET-06 TOR exit node | HIGH | 0.95 | REVIEW |
| DET-07 new destination | LOW | 0.3 | MONITOR |

### New DEFAULT_CONFIG Keys (config.py)
```python
# Source: DET-08 requirement — all thresholds must be named constants in config
DEFAULT_CONFIG = {
    # ... existing keys unchanged ...
    "connection_rate_threshold_per_min": 100,  # DET-02: connections/min trigger
    "tor_exit_list_path": "data/tor-exit-nodes.txt",  # DET-06: local TOR exit node list
}
```

### New config.yaml documentation
```yaml
# Phase 4: Detection Engine
# connection_rate_threshold_per_min: 100  # DET-02: rate spike trigger (connections/minute per process)
# tor_exit_list_path: data/tor-exit-nodes.txt  # DET-06: local TOR exit node IP list
```

### Allowlist Rule Dict Structure
```python
# ALLOW-01 (process-scoped), ALLOW-02 (global), ALLOW-03 (expiry)
{
    "rule_id": "ALLOW-abc123",
    "process_name": "chrome.exe",          # None for global (ALLOW-02)
    "dst_ip": "142.250.183.14",            # None if matching on hostname
    "dst_hostname": "google.com",          # None if matching on IP
    "expires_at": None,                    # datetime(UTC) or None = permanent (ALLOW-03)
    "created_at": "2026-04-05T12:00:00+00:00",
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Module-level mutable global state | State object passed as parameter | Project convention since Phase 2 | Test isolation: each test creates a fresh `DetectorState()` |
| Per-packet psutil call | Background poller + cache | Phase 2 | Same principle: detection state must survive across calls, not reset per packet |
| JSON flat file storage | PostgreSQL (Phase 5) | PRD upgrade 2026-04-04 | Alert persistence is Phase 5 scope; Phase 4 returns `list[dict]` only |
| 6 detection rules (R001-R007, original PRD) | 10 rules DET-01 to DET-10 | PRD upgrade 2026-04-04 | Adds TOR exit node rule and compound unusual-port rule; confidence field added |
| Alert emitted per-packet | Alert rate-limited (DET-09) | Phase 4 requirement | Prevents alert flooding; max 1 alert per rule per process per second |

**Deprecated/outdated:**
- `connection_rate_threshold: 50` comment in config.yaml says "connections/sec trigger" — this comment is outdated relative to DET-02 which uses connections/min. Add new key; do not modify old key's semantics.

---

## Open Questions

1. **TOR exit list source and commit strategy**
   - What we know: https://check.torproject.org/torbulkexitlist publishes a plain-text list updated every 30 minutes; approximately 1,500 to 2,000 IPs
   - What's unclear: Should a snapshot be committed to `data/tor-exit-nodes.txt` in the repo, or should setup instructions include a download step?
   - Recommendation: Commit a snapshot at development time (acceptable for Phase 4); add a `check_blocklist_freshness()`-style warning if the file is older than 7 days. Automatic refresh script is Phase 7 scope.

2. **Alert output channel for Phase 5 integration**
   - What we know: Phase 5 will persist alerts to PostgreSQL and push via WebSocket
   - What's unclear: Should `detect_event()` return `list[dict]` (worker appends to `app.state.alerts_buffer`), or should worker push to a second `asyncio.Queue`?
   - Recommendation: Return `list[dict]`. Worker accumulates alerts in `app.state.alerts_buffer` (a bounded `deque`). This avoids introducing a second queue and is consistent with how connection events are handled in Phase 5. Phase 5 wires up the persistence and push side.

3. **SUPP-01 testability without Phase 5 API**
   - What we know: SUPP-01 requires the user to suppress a specific alert_id. The PATCH /api/v1/alerts/:id endpoint is Phase 5.
   - Recommendation: Implement `suppressed_alert_ids` set in `DetectorState` and the suppression check in `detect_event()`. Unit-test by directly adding an alert_id to the set. The API binding is Phase 5 scope — documented in the plan as an integration seam.

4. **DET-07 — should private/LAN IPs trigger new-destination alerts?**
   - What we know: A browser makes many connections to LAN IPs (router, printer, NAS) that are "first-ever" on startup.
   - Recommendation: Suppress DET-07 for RFC1918 addresses (`ipaddress.ip_address(dst_ip).is_private`). The rule's value is detecting unexpected external destinations, not known LAN devices. Document this as a design decision.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | All detection logic | Yes | 3.11.0 | — |
| `uuid` stdlib | DET-10 alert_id | Built-in | stdlib | — |
| `datetime` stdlib | DET-10, ALLOW-03 | Built-in | stdlib | — |
| `time` stdlib | DET-09 rate limiter | Built-in | stdlib | — |
| `dataclasses` stdlib | DetectorState | Built-in | stdlib | — |
| `ipaddress` stdlib | DET-01, DET-07 private IP guard | Built-in | stdlib | — |
| `pytest` + `pytest-asyncio` | Test suite | Already installed | 8.0+ / 0.23+ | — |
| `data/tor-exit-nodes.txt` | DET-06 | Must exist | — | If missing: log WARNING, DET-06 disabled (`tor_exit_nodes = frozenset()`) |

**Missing dependencies with no fallback:** None — all required packages are stdlib or already in requirements.txt.

**Missing dependencies with fallback:**
- `data/tor-exit-nodes.txt`: If missing, `load_tor_exit_nodes()` returns an empty frozenset and logs a WARNING. DET-06 is disabled but all other rules function normally.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.23+ |
| Config file | `pytest.ini` (exists — `asyncio_mode = auto`, `testpaths = tests`) |
| Quick run command | `pytest tests/test_pipeline/test_detector.py -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-01 | Unknown domain emits WARNING | unit | `pytest tests/test_pipeline/test_detector.py::test_det01_unknown_domain -x` | No — Wave 0 |
| DET-02 | >100 connections/min triggers HIGH | unit | `pytest tests/test_pipeline/test_detector.py::test_det02_rate_spike -x` | No — Wave 0 |
| DET-03 | Unusual port + unknown process alerts; known process does not | unit | `pytest tests/test_pipeline/test_detector.py::test_det03_compound_rule -x` | No — Wave 0 |
| DET-04 | "unknown process" emits ALERT | unit | `pytest tests/test_pipeline/test_detector.py::test_det04_unknown_process -x` | No — Wave 0 |
| DET-05 | Blocklisted IP emits CRITICAL | unit | `pytest tests/test_pipeline/test_detector.py::test_det05_blocklisted -x` | No — Wave 0 |
| DET-06 | TOR exit node IP emits HIGH | unit | `pytest tests/test_pipeline/test_detector.py::test_det06_tor_exit_node -x` | No — Wave 0 |
| DET-07 | First-ever destination emits LOW | unit | `pytest tests/test_pipeline/test_detector.py::test_det07_new_destination -x` | No — Wave 0 |
| DET-08 | No magic numbers — all from config | code review | Verified by grep for hardcoded literals in detector.py | No — Wave 0 |
| DET-09 | Rate limiter: max 1 alert/rule/process/sec | unit | `pytest tests/test_pipeline/test_detector.py::test_det09_rate_limiter -x` | No — Wave 0 |
| DET-10 | All 12 alert fields present | unit | `pytest tests/test_pipeline/test_detector.py::test_det10_alert_fields -x` | No — Wave 0 |
| ALLOW-01 | Process-scoped allowlist suppresses alert | unit | `pytest tests/test_pipeline/test_detector.py::test_allow01_process_scoped -x` | No — Wave 0 |
| ALLOW-02 | Global allowlist suppresses alert for any process | unit | `pytest tests/test_pipeline/test_detector.py::test_allow02_global -x` | No — Wave 0 |
| ALLOW-03 | Expired allowlist rule does not suppress | unit | `pytest tests/test_pipeline/test_detector.py::test_allow03_expiry -x` | No — Wave 0 |
| ALLOW-04 | Allowlist check fires before alert construction | unit | `pytest tests/test_pipeline/test_detector.py::test_allow04_pre_check -x` | No — Wave 0 |
| SUPP-01 | Single alert_id suppression marks alert suppressed | unit | `pytest tests/test_pipeline/test_detector.py::test_supp01_instance -x` | No — Wave 0 |
| SUPP-02 | Rule+process suppression marks future alerts suppressed | unit | `pytest tests/test_pipeline/test_detector.py::test_supp02_rule_process -x` | No — Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_pipeline/test_detector.py -v`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline/test_detector.py` — covers all 16 requirements above (does not exist yet)
- [ ] `data/tor-exit-nodes.txt` — required for DET-06 tests (use a small fixture file with 3-5 test IPs for unit tests; mock in other tests)

*(Existing infrastructure: `pytest.ini`, `tests/conftest.py`, `pytest-asyncio` — all present and correct. No framework gaps.)*

---

## Sources

### Primary (HIGH confidence)
- Existing codebase: `pnpg/pipeline/threat_intel.py` — `frozenset` pattern for TOR list (verified by reading)
- Existing codebase: `pnpg/pipeline/dns_resolver.py` — `time.monotonic()` rate-timing pattern (verified by reading)
- Existing codebase: `pnpg/pipeline/worker.py` — pipeline integration pattern, stub comment location (verified by reading)
- Existing codebase: `pnpg/config.py` — `DEFAULT_CONFIG` structure, existing keys (verified by reading)
- Existing codebase: `pnpg/main.py` — lifespan pattern for resource init and app.state (verified by reading)
- `REQUIREMENTS.md` "Alert Object (Production Schema)" — DET-10 field spec (verified by reading)
- `REQUIREMENTS.md` "Detection" section — DET-01 through DET-10 exact spec text (verified by reading)
- Python 3.11 stdlib: `uuid`, `datetime`, `time`, `dataclasses`, `ipaddress`, `collections.defaultdict` — stable, well-known APIs (HIGH confidence)

### Secondary (MEDIUM confidence)
- Tor Project bulk exit list format: https://check.torproject.org/torbulkexitlist — one IPv4 per line, no header (training data knowledge; verify format when downloading)
- Sliding window rate counter pattern: standard algorithm, widely documented (no single source; HIGH confidence in correctness)

### Tertiary (LOW confidence — not applicable)
- No LOW confidence findings in this research. All patterns are either drawn from the existing codebase or from Python stdlib documentation.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib; no new packages; verified against installed Python 3.11.0
- Architecture: HIGH — follows established project patterns from Phases 1-3 exactly; no novel patterns introduced
- Pitfalls: HIGH — DET-03 false-positive and rate-limiter ordering pitfalls are explicit in the spec's success criteria; datetime timezone pitfall is a well-known Python gotcha; others derived from direct code analysis

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable domain — Python stdlib does not change; codebase patterns are fixed)
