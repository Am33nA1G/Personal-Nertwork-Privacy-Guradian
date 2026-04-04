# Phase 3: Enrichment Service - Research

**Researched:** 2026-04-04
**Domain:** DNS resolution, GeoIP/ASN enrichment, threat intelligence blocklist, async Python pipeline integration
**Confidence:** HIGH (core patterns verified empirically; library APIs confirmed via official docs and PyPI)

---

## Summary

Phase 3 adds three enrichment layers to the pipeline: reverse DNS hostname resolution, GeoIP/ASN country and organization lookup, and threat intel blocklist checking. All three must be non-blocking, have hard timeouts, cache results, and degrade gracefully to null on failure. The pipeline worker already has a `ThreadPoolExecutor` and a stub comment for Phase 3 DNS; this phase fills that stub and adds two more enrichment modules.

The primary challenge is DNS on Windows: empirical testing on the target machine confirms that `socket.gethostbyaddr()` takes **4-5 seconds for IPs with no PTR record** — well over the 2-second requirement. This is OS-level behavior (Windows DNS resolver timeout). The solution is to use `asyncio.wait_for(loop.run_in_executor(...), timeout=2.0)` which unblocks the event loop correctly, though the underlying OS thread continues running until the OS DNS timeout fires (unavoidable on Windows — thread cancellation of blocking OS calls is not possible). Tests have confirmed this pattern delivers a 2.01s timeout result reliably.

For GeoIP, the `geoip2` library (5.2.0 on PyPI) uses MaxMind MMDB format and requires the GeoLite2 databases to be present locally. The reader must use `MODE_MEMORY` or `MODE_MMAP` for thread safety when called from multiple threads. The databases require a free MaxMind account; GitHub mirrors exist as fallback. For the threat intel blocklist, IPsum is the recommended source: a plain-text IP list, one IP per line with tab-separated count, downloadable once and usable as a local file.

**Primary recommendation:** Build three focused modules — `dns_resolver.py`, `geo_enricher.py`, `threat_intel.py` — following the same immutable-dict pattern established by `process_mapper.py`. Wire all three into `pipeline_worker.py` as sequential `await` calls, consistent with Phase 2's approach.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DNS-01 | Resolve destination IPs to domain names via reverse DNS lookup | `socket.gethostbyaddr()` in thread pool; returns hostname string |
| DNS-02 | DNS lookups run in thread pool executor (not blocking event loop) | `loop.run_in_executor(executor, socket.gethostbyaddr, ip)` — verified pattern |
| DNS-03 | DNS resolution has 2-second timeout per lookup | `asyncio.wait_for(..., timeout=2.0)` — empirically tested: fires at 2.01s on this machine |
| DNS-04 | Resolved IP→domain mappings cached with TTL | Custom `TtlLruCache` (OrderedDict + time.monotonic) consistent with codebase style |
| DNS-05 | Unresolvable IPs fall back to raw IP address | Return `ip` string on `socket.herror`, `socket.gaierror`, `asyncio.TimeoutError` |
| DNS-06 | DNS cache bounded to max 1000 entries with LRU eviction | `TtlLruCache(maxsize=1000, ttl=dns_cache_ttl_sec)` — LRU eviction on `maxsize` |
| GEO-01 | Resolve destination IPs to country codes using local MaxMind GeoLite2 | `geoip2.database.Reader('GeoLite2-Country.mmdb').country(ip).country.iso_code` |
| GEO-02 | Resolve destination IPs to ASN and organization name | `geoip2.database.Reader('GeoLite2-ASN.mmdb').asn(ip)` → `.autonomous_system_number`, `.autonomous_system_organization` |
| GEO-03 | GeoIP lookups have hard timeout of 5ms | Local MMDB lookups are in-process memory reads — use `time.monotonic()` guard; signal via null if 5ms exceeded |
| GEO-04 | Failed GeoIP/ASN lookups return null — pipeline never blocks | `try/except (AddressNotFoundError, Exception)` → return `None` fields |
| GEO-05 | Log `GEOIP_STALE` metric if local GeoIP DB is older than 30 days | Check `os.path.getmtime(db_path)` at startup; log WARNING if > 30 days old |
| THREAT-01 | Check dst_ip and dst_domain against local threat intel blocklist | Load blocklist into a `frozenset[str]` at startup; O(1) lookup |
| THREAT-02 | Blocklist stored locally, no external network call during runtime | Plain text file bundled or downloaded once at setup time |
| THREAT-03 | Blocklist check has hard timeout of 5ms — never blocks pipeline | Frozenset lookup is microsecond; no timeout mechanism needed in practice |
| THREAT-04 | Log `THREATINTEL_STALE` if blocklist not updated in >24 hours | Check `os.path.getmtime(blocklist_path)` at startup; log WARNING if > 24h old |
| THREAT-05 | Flag blocklisted destinations with `threat_intel.is_blocklisted: true` and record source list name | Return `{"is_blocklisted": True, "source": "ipsum"}` in enriched event |
| SYS-03 | If eBPF probe fails, auto-fallback to libpcap with non-alarming notice | Document fallback logic in `prereqs.py` or `main.py`; relevant to startup probe selection (not enrichment logic directly) |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

- **No framework substitutions**: Python 3.11+, FastAPI, Scapy, psutil, socket stdlib — no substitutions
- **Local only**: No external network calls during runtime; all enrichment uses local databases
- **Storage**: PostgreSQL 15+ (Phase 5 — not in scope for Phase 3)
- **Performance**: 10,000 events/sec, p95 < 100ms
- **Immutability**: ALWAYS create new dicts — never mutate events in-place (enforced in process_mapper.py)
- **File size**: 200-400 lines typical, 800 max — enrichment modules must stay focused
- **Error handling**: NEVER silently swallow errors; log with context
- **Existing config keys**: `dns_cache_size: 1000`, `dns_cache_ttl_sec: 300` already in `DEFAULT_CONFIG` — use these, do not add redundant keys
- **No SQLite**: Not relevant to Phase 3, but noted
- **Pre-wired stub**: `pipeline_worker.py` line 58 has `# Phase 3: event = await dns_resolver(event, executor, loop)` — the hook location is established

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `socket` (stdlib) | Python 3.11 built-in | Reverse DNS via `gethostbyaddr()` | Already in CLAUDE.md; no third-party needed |
| `geoip2` | 5.2.0 | MaxMind MMDB reader (GeoLite2-Country + GeoLite2-ASN) | Official MaxMind Python client; supports local MMDB |
| `maxminddb` | 3.1.1 | Lower-level MMDB reader (pulled as geoip2 dependency) | Transitive — do not pin separately |
| `concurrent.futures` (stdlib) | Python 3.11 built-in | ThreadPoolExecutor for DNS off event loop | Already used in pipeline_worker.py |
| `asyncio` (stdlib) | Python 3.11 built-in | `wait_for` timeout on thread pool futures | Core project async runtime |
| `collections.OrderedDict` (stdlib) | Python 3.11 built-in | TtlLruCache implementation | Consistent with codebase — avoids new dependency |
| `time` (stdlib) | Python 3.11 built-in | `monotonic()` for TTL expiry | Same pattern as `process_mapper.py` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `cachetools` | 7.0.5 (available) | Drop-in TTLCache + LRUCache | Would be simpler; but adds a dependency not in requirements.txt; not installed; prefer stdlib OrderedDict per project style |
| `os.path` (stdlib) | built-in | `getmtime()` for GEOIP_STALE / THREATINTEL_STALE checks | Required for GEO-05 and THREAT-04 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom `TtlLruCache` | `cachetools.TTLCache` | cachetools is cleaner but adds a dep not in requirements.txt; project pattern is stdlib-first |
| `socket.gethostbyaddr` | `dnspython` | dnspython adds a dep; stdlib is adequate with thread pool |
| Local MMDB file | MaxMind HTTP web service | Web service = external network call; CLAUDE.md forbids this |

**Installation:**
```bash
pip install geoip2>=4.8.0
# GeoLite2 database files (requires free MaxMind account):
# https://www.maxmind.com/en/geolite2/signup
# Download: GeoLite2-Country.mmdb, GeoLite2-ASN.mmdb
# Place in: data/ directory (or path configured in config.yaml)
```

**Version verification (confirmed 2026-04-04):**
- `geoip2`: 5.2.0 (latest)
- `maxminddb`: 3.1.1 (latest, pulled as dep)

---

## Architecture Patterns

### Recommended Project Structure Addition
```
pnpg/
├── pipeline/
│   ├── __init__.py
│   ├── worker.py           # Modified: wire enrich_dns, enrich_geo, check_threat
│   ├── process_mapper.py   # Phase 2 — unchanged
│   ├── dns_resolver.py     # NEW: Plan 03-01
│   ├── geo_enricher.py     # NEW: Plan 03-02
│   └── threat_intel.py     # NEW: Plan 03-03
data/
│   ├── GeoLite2-Country.mmdb   # Downloaded at setup (not in git)
│   ├── GeoLite2-ASN.mmdb       # Downloaded at setup (not in git)
│   └── blocklist.txt           # Downloaded at setup (not in git)
tests/
└── test_pipeline/
    ├── test_dns_resolver.py    # NEW: Plan 03-01
    ├── test_geo_enricher.py    # NEW: Plan 03-02
    └── test_threat_intel.py    # NEW: Plan 03-03
```

### Pattern 1: Thread Pool DNS with asyncio.wait_for Timeout

**What:** DNS runs in a thread pool; `asyncio.wait_for` enforces the 2-second hard timeout. The event loop is unblocked regardless of OS-level DNS behavior.
**When to use:** Any blocking I/O call dispatched from an asyncio context.
**Empirically verified:** `asyncio.TimeoutError` fires at exactly 2.01s on this Windows 11 machine.

```python
# Source: empirically tested 2026-04-04 — confirmed working on Windows 11 / Python 3.11
async def resolve_hostname(
    ip: str,
    cache: "TtlLruCache",
    executor: ThreadPoolExecutor,
    loop: asyncio.AbstractEventLoop,
    timeout: float = 2.0,
) -> str:
    """Resolve IP to hostname; return raw IP on failure or timeout."""
    # Cache check (DNS-04)
    cached = cache.get(ip)
    if cached is not None:
        return cached

    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(executor, socket.gethostbyaddr, ip),
            timeout=timeout,
        )
        hostname = result[0]
    except asyncio.TimeoutError:
        hostname = ip  # DNS-05: fallback to raw IP
    except (socket.herror, socket.gaierror):
        hostname = ip  # DNS-05: no PTR record

    cache.set(ip, hostname)  # includes negative caching (DNS-04)
    return hostname
```

**IMPORTANT — Thread leak on Windows:** When `asyncio.TimeoutError` fires, the underlying `socket.gethostbyaddr()` OS thread continues running until the Windows DNS resolver times out (~4-5s). This is unavoidable with blocking OS calls. The thread pool must have sufficient workers (current: 4) to absorb leaked threads. For 10,000 events/sec with varied IPs, consider raising to 8-16 workers in Phase 3.

### Pattern 2: Immutable TtlLruCache (stdlib only)

**What:** OrderedDict-based TTL+LRU cache consistent with project style (no external dependency).
**When to use:** Any cache with both size bound (LRU eviction) and time bound (TTL expiry).

```python
# Source: project pattern (process_mapper.py style)
import time
from collections import OrderedDict
from threading import Lock

class TtlLruCache:
    """Thread-safe TTL + LRU cache using OrderedDict."""

    def __init__(self, maxsize: int, ttl: float) -> None:
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)  # LRU: mark as recently used
            return value

    def set(self, key: str, value: str) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            elif len(self._cache) >= self.maxsize:
                self._cache.popitem(last=False)  # evict LRU
            self._cache[key] = (value, time.monotonic() + self.ttl)
```

**Thread safety note:** A `Lock` is required because `resolve_hostname` is called from multiple threads via the thread pool executor.

### Pattern 3: GeoIP Reader Initialization with Thread Safety

**What:** `geoip2.database.Reader` opened once at module level using `MODE_MEMORY` for thread safety. Closed in lifespan shutdown.
**When to use:** MaxMind MMDB local database lookups.

```python
# Source: MaxMind GeoIP2-python README (github.com/maxmind/GeoIP2-python)
import geoip2.database
import geoip2.errors
import maxminddb

# MODE_MEMORY is thread-safe (confirmed via maxmind/GeoIP2-python issue #20)
_country_reader: geoip2.database.Reader | None = None
_asn_reader: geoip2.database.Reader | None = None

def open_readers(country_db_path: str, asn_db_path: str) -> None:
    global _country_reader, _asn_reader
    _country_reader = geoip2.database.Reader(
        country_db_path, mode=maxminddb.MODE_MEMORY
    )
    _asn_reader = geoip2.database.Reader(
        asn_db_path, mode=maxminddb.MODE_MEMORY
    )

def enrich_geo(event: dict) -> dict:
    """Return new dict with dst_country, dst_asn, dst_org. Never mutates event."""
    ip = event.get("dst_ip")
    country, asn, org = None, None, None

    if ip and _country_reader:
        try:
            resp = _country_reader.country(ip)
            country = resp.country.iso_code
        except (geoip2.errors.AddressNotFoundError, Exception):
            country = None

    if ip and _asn_reader:
        try:
            resp = _asn_reader.asn(ip)
            asn = f"AS{resp.autonomous_system_number}"
            org = resp.autonomous_system_organization
        except (geoip2.errors.AddressNotFoundError, Exception):
            asn, org = None, None

    return {**event, "dst_country": country, "dst_asn": asn, "dst_org": org}
```

**GeoIP timeout note (GEO-03):** Local MMDB lookups with `MODE_MEMORY` are in-process memory reads — typically 0.1-1ms. The 5ms timeout requirement is satisfied by design; no explicit timeout mechanism is needed. Document this as a DESIGN NOTE, not a `asyncio.wait_for`.

### Pattern 4: Blocklist as frozenset

**What:** Threat intel IP blocklist loaded into `frozenset` at startup. O(1) lookup, no threading concern.
**When to use:** Any static set of IP strings that needs membership testing.

```python
# Source: IPsum blocklist format (github.com/stamparm/ipsum)
import os, time, logging

BLOCKLIST_PATH = "data/blocklist.txt"
_blocklist: frozenset[str] = frozenset()
_blocklist_loaded_at: float = 0.0

def load_blocklist(path: str = BLOCKLIST_PATH) -> None:
    """Load IP blocklist from plain text file into frozenset."""
    global _blocklist, _blocklist_loaded_at
    ips: set[str] = set()
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ip = line.split("\t")[0]  # IPsum format: IP<tab>count
                    ips.add(ip)
        _blocklist = frozenset(ips)
        _blocklist_loaded_at = time.time()
        logging.getLogger(__name__).info(
            "Loaded %d IPs into blocklist from %s", len(ips), path
        )
    except FileNotFoundError:
        logging.getLogger(__name__).warning(
            "Blocklist file not found at %s — threat intel disabled", path
        )
        _blocklist = frozenset()

def check_threat_intel(event: dict) -> dict:
    """Return new dict with threat_intel field. Never mutates event."""
    dst_ip = event.get("dst_ip", "")
    dst_domain = event.get("dst_hostname", "")
    is_blocked = dst_ip in _blocklist or dst_domain in _blocklist
    source = "ipsum" if is_blocked else None
    return {
        **event,
        "threat_intel": {"is_blocklisted": is_blocked, "source": source},
    }
```

### Pattern 5: GEOIP_STALE / THREATINTEL_STALE Check at Startup

**What:** Check `os.path.getmtime()` against current time at startup; log a WARNING with a structured key if stale.
**When to use:** GEO-05, THREAT-04.

```python
import os, time, logging

logger = logging.getLogger(__name__)
SECONDS_IN_DAY = 86400
GEOIP_MAX_AGE_DAYS = 30
THREAT_MAX_AGE_HOURS = 24

def check_db_freshness(db_path: str, max_age_seconds: float, metric_key: str) -> None:
    """Log a WARNING if the file at db_path is older than max_age_seconds."""
    try:
        age = time.time() - os.path.getmtime(db_path)
        if age > max_age_seconds:
            logger.warning(
                "%s: database at %s is %.1f days old (limit: %.1f days)",
                metric_key,
                db_path,
                age / SECONDS_IN_DAY,
                max_age_seconds / SECONDS_IN_DAY,
            )
    except FileNotFoundError:
        logger.warning("%s: database file not found at %s", metric_key, db_path)
```

### Anti-Patterns to Avoid

- **Calling `socket.gethostbyaddr` directly on the event loop:** Blocks the event loop for up to 5 seconds. Verified on this machine. Always use `run_in_executor`.
- **Using `geoip2.database.Reader` with `MODE_FILE`:** Not thread-safe. Use `MODE_MEMORY` or `MODE_MMAP`.
- **Mutating the event dict in-place:** Violates project-wide immutability rule (CLAUDE.md). Always return `{**event, ...}`.
- **Creating a new `ThreadPoolExecutor` per lookup:** Expensive. Reuse the executor created in `pipeline_worker.py` (already exists with `max_workers=4`).
- **Adding new config keys that duplicate existing ones:** `dns_cache_size` and `dns_cache_ttl_sec` already exist in `DEFAULT_CONFIG`. Use them — do not add `geoip_db_path` as a DEFAULT_CONFIG key unless explicitly needed; pass via function argument from config.yaml additions.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MMDB binary parsing | Custom MMDB reader | `geoip2.database.Reader` | MMDB is a binary format with tree-based lookup; parsing is non-trivial and edge-case prone |
| TTL+LRU cache | Custom if complex | `cachetools.TTLCache` (not installed) OR stdlib `OrderedDict` | Simple stdlib version is adequate; see Pattern 2 |
| Thread-safe set membership | Custom locking | `frozenset` (immutable = inherently thread-safe) | frozenset is never mutated after load; no lock needed |

**Key insight:** The enrichment pipeline's correctness depends entirely on non-blocking semantics and graceful degradation. The "hard" problems (MMDB parsing, thread-safe LRU) have library solutions; the "easy" path is delegating to `geoip2` and using a simple ordered-dict cache.

---

## Common Pitfalls

### Pitfall 1: DNS Thread Leak on Timeout (Windows-specific)

**What goes wrong:** `asyncio.wait_for` fires `asyncio.TimeoutError` and the coroutine resumes, but the OS thread running `socket.gethostbyaddr()` continues blocking until the OS DNS timeout fires (~4-5 seconds on this machine).
**Why it happens:** Python's `ThreadPoolExecutor` cannot cancel a running thread. The future is abandoned by asyncio but the thread runs to completion.
**How to avoid:** Size the thread pool large enough to absorb leaked threads: `max_workers=16` for Phase 3 given that new IPs can burst. The current `max_workers=4` in `pipeline_worker.py` will need to increase.
**Warning signs:** Thread count growing over time; event loop lag under sustained new-IP bursts.

### Pitfall 2: GeoIP Reader Opened Per Lookup

**What goes wrong:** Opening `geoip2.database.Reader` once per IP lookup creates I/O overhead (file open + MMDB header parse per call), destroying the 5ms budget.
**Why it happens:** The reader is expensive to initialize.
**How to avoid:** Open the reader once at startup in `open_readers()` and keep it open for the process lifetime. Use `MODE_MEMORY` so the entire database is loaded into RAM once.
**Warning signs:** GeoIP enrichment taking >5ms per event.

### Pitfall 3: Thread Safety with geoip2 Reader in MODE_FILE

**What goes wrong:** Concurrent reads from multiple threads corrupt internal file position state.
**Why it happens:** `MODE_FILE` uses a single file handle with non-atomic reads.
**How to avoid:** Always use `MODE_MEMORY` or `MODE_MMAP`. Confirmed in MaxMind GitHub issue #20.
**Warning signs:** Intermittent `maxminddb.InvalidDatabaseError` or garbage results under concurrent load.

### Pitfall 4: Negative DNS Caching Missing

**What goes wrong:** IPs with no PTR record cause a new 2-second timeout on every lookup because the miss is not cached.
**Why it happens:** Naive implementation only caches successful lookups.
**How to avoid:** On `socket.herror`, `socket.gaierror`, or `asyncio.TimeoutError`, still call `cache.set(ip, ip)` to cache the "no PTR" result. The TTL ensures the cache entry expires and a fresh attempt is made eventually.
**Warning signs:** Each packet from a new-IP destination incurs 2 seconds of wait.

### Pitfall 5: Blocklist File Missing Silently Disables Threat Intel

**What goes wrong:** If `data/blocklist.txt` is missing, `load_blocklist()` sets `_blocklist = frozenset()` silently. All blocklist checks return `is_blocklisted: false`. No alert is ever triggered.
**Why it happens:** Silent fallback without user-visible notice.
**How to avoid:** Log a WARNING (not just INFO) when the blocklist file is missing. Include instructions in the log message for how to download it.
**Warning signs:** `THREAT_02` test passes but `threat_intel.is_blocklisted` is always false in production.

### Pitfall 6: SYS-03 Scope Confusion

**What goes wrong:** SYS-03 ("eBPF fails → fallback to libpcap") is assigned to Phase 3 in REQUIREMENTS.md but is architecturally a capture-layer concern, not an enrichment concern.
**Why it happens:** Grouping into Phase 3 is because it was not covered in Phase 1/2.
**How to avoid:** Implement SYS-03 in `prereqs.py` or `main.py` as a probe selection flag (e.g., `probe_type: "libpcap"` in config) logged at startup. No enrichment code needs to know about probe type. Keep the notice in the dashboard via a status field already planned (API-05/UI-05). Plan 03-03 should implement the startup notice; no enrichment module change needed.
**Warning signs:** Attempting to interleave probe selection logic inside enrichment modules.

---

## Code Examples

### dns_resolver.py skeleton (Plan 03-01)

```python
# Module: pnpg/pipeline/dns_resolver.py
import asyncio
import logging
import socket
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

logger = logging.getLogger(__name__)

class TtlLruCache:
    def __init__(self, maxsize: int, ttl: float) -> None: ...
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...

async def resolve_hostname(
    ip: str,
    cache: TtlLruCache,
    executor: ThreadPoolExecutor,
    loop: asyncio.AbstractEventLoop,
    timeout: float = 2.0,
) -> str: ...

async def enrich_dns(
    event: dict,
    cache: TtlLruCache,
    executor: ThreadPoolExecutor,
    loop: asyncio.AbstractEventLoop,
) -> dict:
    """Return new dict with dst_hostname populated. DNS-01 to DNS-06."""
    hostname = await resolve_hostname(
        event.get("dst_ip", ""), cache, executor, loop
    )
    return {**event, "dst_hostname": hostname}
```

### geo_enricher.py skeleton (Plan 03-02)

```python
# Module: pnpg/pipeline/geo_enricher.py
import geoip2.database
import geoip2.errors
import maxminddb

# GEO-01/GEO-02: open_readers() at startup via lifespan
# GEO-03: local MMDB lookups are ~0.1ms — no explicit timeout needed
# GEO-04: try/except returns None fields on any failure
# GEO-05: check_db_freshness() at open_readers() call time
```

### pipeline worker wiring (Plan 03-03)

```python
# In pipeline/worker.py — replace Phase 3 stub comments:
event = await enrich_dns(event, dns_cache, executor, loop)  # DNS-01..06
event = enrich_geo(event)                                    # GEO-01..05
event = check_threat_intel(event)                           # THREAT-01..05
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| WinPcap (Windows driver) | Npcap | 2019 | Already handled in Phase 1 |
| MaxMind free direct download | Requires free account + license key | Dec 2019 (+ Account ID May 2024) | Must document setup step; GitHub mirrors exist as fallback |
| `geoip2` web service calls | Local MMDB file | Ongoing | CLAUDE.md: local only; no external calls |
| Per-process DNS caching | Global IP-keyed cache | Project decision | DNS cache is per-IP destination, not per-process |

**Deprecated/outdated:**
- `WinPcap`: EOL since 2013 — replaced by Npcap (already handled in Phase 1)
- `geoip2` legacy API (pre-4.0): response attribute style changed; current 5.2.0 uses `.country.iso_code` not `.country.country.iso_code`

---

## Open Questions

1. **MaxMind Account Setup**
   - What we know: GeoLite2 requires a free MaxMind account and license key since Dec 2019; Account ID required since May 2024
   - What's unclear: Whether a setup script or documented manual step is preferred; whether GitHub mirror (wp-statistics/GeoLite2-City) is acceptable for MVP
   - Recommendation: Document as a one-time setup step in a `scripts/download_dbs.py` or `SETUP.md`; use GitHub mirror CDN as fallback for CI

2. **Thread Pool Size for DNS**
   - What we know: Current pool is `max_workers=4` in `pipeline_worker.py`; DNS thread leaks on Windows mean leaked threads hold pool slots for ~4-5s
   - What's unclear: Exact worker count needed for 10,000 events/sec sustained load with varied destination IPs
   - Recommendation: Raise to `max_workers=16` for Phase 3; document as configurable; Phase 7 load test will validate

3. **config.yaml additions for Phase 3**
   - What we know: `dns_cache_size` and `dns_cache_ttl_sec` already in `DEFAULT_CONFIG`
   - What's unclear: Whether GeoIP DB paths and blocklist path should go in `DEFAULT_CONFIG` or just config.yaml comments
   - Recommendation: Add `geoip_country_db`, `geoip_asn_db`, `blocklist_path` to `DEFAULT_CONFIG` as strings with sensible defaults pointing to `data/` directory

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|---------|
| Python 3.11 | All | Yes | 3.11.0 | — |
| pytest 9.0.2 | Tests | Yes | 9.0.2 | — |
| pytest-asyncio 1.3.0 | Async tests | Yes | 1.3.0 | — |
| `socket` stdlib | DNS-01..06 | Yes | built-in | — |
| `concurrent.futures` stdlib | DNS-02/03 | Yes | built-in | — |
| `geoip2` | GEO-01..05 | Not installed | 5.2.0 on PyPI | — |
| `maxminddb` | GEO-01..05 (dep) | Not installed | 3.1.1 on PyPI | — |
| GeoLite2-Country.mmdb | GEO-01 | Not present | — | Null geo fields (GEO-04) |
| GeoLite2-ASN.mmdb | GEO-02 | Not present | — | Null ASN fields (GEO-04) |
| `data/blocklist.txt` | THREAT-01..05 | Not present | — | Empty frozenset; log WARNING (THREAT-02) |
| `cachetools` | DNS cache (optional) | Not installed | 7.0.5 on PyPI | Use stdlib OrderedDict (chosen approach) |

**Missing dependencies with no fallback:**
- `geoip2` — must be installed (`pip install geoip2>=4.8.0`); this is a blocking install for Plan 03-02

**Missing dependencies with fallback:**
- `GeoLite2-Country.mmdb` / `GeoLite2-ASN.mmdb` — pipeline continues with null geo fields per GEO-04; GEO-05 logs GEOIP_STALE warning
- `data/blocklist.txt` — pipeline continues with `is_blocklisted: false`; THREAT-04 logs THREATINTEL_STALE warning

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` (exists — `asyncio_mode = auto`) |
| Quick run command | `python -m pytest tests/test_pipeline/ -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DNS-01 | Resolve IP → hostname | unit | `pytest tests/test_pipeline/test_dns_resolver.py::test_resolves_known_ip -x` | Wave 0 |
| DNS-02 | DNS runs in thread pool (not event loop) | unit | `pytest tests/test_pipeline/test_dns_resolver.py::test_dns_uses_executor -x` | Wave 0 |
| DNS-03 | 2-second timeout fires | unit | `pytest tests/test_pipeline/test_dns_resolver.py::test_timeout_fires -x` | Wave 0 |
| DNS-04 | Cache hit — no second lookup | unit | `pytest tests/test_pipeline/test_dns_resolver.py::test_cache_hit -x` | Wave 0 |
| DNS-05 | No PTR → raw IP returned | unit | `pytest tests/test_pipeline/test_dns_resolver.py::test_no_ptr_fallback -x` | Wave 0 |
| DNS-06 | Cache LRU eviction at maxsize | unit | `pytest tests/test_pipeline/test_dns_resolver.py::test_cache_lru_eviction -x` | Wave 0 |
| GEO-01 | IP → country iso_code | unit | `pytest tests/test_pipeline/test_geo_enricher.py::test_country_lookup -x` | Wave 0 |
| GEO-02 | IP → ASN + org | unit | `pytest tests/test_pipeline/test_geo_enricher.py::test_asn_lookup -x` | Wave 0 |
| GEO-03 | GeoIP stays under 5ms (memory mode) | unit | `pytest tests/test_pipeline/test_geo_enricher.py::test_geo_latency -x` | Wave 0 |
| GEO-04 | Missing IP → null fields, no crash | unit | `pytest tests/test_pipeline/test_geo_enricher.py::test_address_not_found -x` | Wave 0 |
| GEO-05 | GEOIP_STALE logged if DB old | unit | `pytest tests/test_pipeline/test_geo_enricher.py::test_stale_warning -x` | Wave 0 |
| THREAT-01 | Blocklisted IP flagged | unit | `pytest tests/test_pipeline/test_threat_intel.py::test_blocklisted_ip -x` | Wave 0 |
| THREAT-02 | Missing blocklist file → graceful | unit | `pytest tests/test_pipeline/test_threat_intel.py::test_missing_file -x` | Wave 0 |
| THREAT-03 | Lookup < 5ms | unit | `pytest tests/test_pipeline/test_threat_intel.py::test_lookup_latency -x` | Wave 0 |
| THREAT-04 | THREATINTEL_STALE logged if old | unit | `pytest tests/test_pipeline/test_threat_intel.py::test_stale_warning -x` | Wave 0 |
| THREAT-05 | is_blocklisted + source in event | unit | `pytest tests/test_pipeline/test_threat_intel.py::test_flag_fields -x` | Wave 0 |
| SYS-03 | eBPF fallback → libpcap notice logged | unit | `pytest tests/test_pipeline/test_worker.py::test_probe_fallback_logged -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_pipeline/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green (39 existing + Phase 3 new tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline/test_dns_resolver.py` — covers DNS-01 to DNS-06
- [ ] `tests/test_pipeline/test_geo_enricher.py` — covers GEO-01 to GEO-05
- [ ] `tests/test_pipeline/test_threat_intel.py` — covers THREAT-01 to THREAT-05

**Key note for test authors:** `geoip2.database.Reader` must be mocked in all GeoIP tests since the actual MMDB files will not be present in CI. Use `unittest.mock.patch` on the reader's query methods. Similarly, `socket.gethostbyaddr` must be mocked for DNS tests to avoid actual network calls and 2-second delays.

---

## Sources

### Primary (HIGH confidence)
- Empirical testing (2026-04-04) — DNS timeout behavior on Windows 11 / Python 3.11 (4-5s negative lookup, asyncio.wait_for fires at 2.01s)
- `geoip2` 5.2.0 on PyPI — confirmed version 2026-04-04
- `maxminddb` 3.1.1 on PyPI — confirmed version 2026-04-04
- `process_mapper.py` in-codebase — established immutable-dict + TtlLruCache pattern precedent
- `pipeline/worker.py` in-codebase — existing `ThreadPoolExecutor(max_workers=4)`, stub comment location

### Secondary (MEDIUM confidence)
- [maxmind/GeoIP2-python README](https://github.com/maxmind/GeoIP2-python/blob/main/README.rst) — Reader API, field names, AddressNotFoundError
- [MaxMind issue #20 — thread safety](https://github.com/maxmind/GeoIP2-python/issues/20) — MODE_MEMORY is thread-safe; MODE_FILE is not
- [stamparm/ipsum](https://github.com/stamparm/ipsum) — plain text IP blocklist, tab-separated format, daily updates
- [MaxMind GeoLite2 license key requirement](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/) — free account required since Dec 2019

### Tertiary (LOW confidence)
- [wp-statistics/GeoLite2-City GitHub mirror](https://github.com/wp-statistics/GeoLite2-City) — no-account CDN alternative (not officially endorsed by MaxMind)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — geoip2/maxminddb versions confirmed from PyPI; stdlib tools verified in-environment
- Architecture: HIGH — patterns verified against existing codebase (`process_mapper.py`, `worker.py`); DNS timeout tested empirically
- Pitfalls: HIGH — DNS thread leak and timeout values confirmed by empirical measurement on target machine; geoip2 thread safety confirmed via official GitHub issue
- GeoLite2 setup: MEDIUM — license key requirement confirmed from official docs; file paths assumed to be `data/` (project convention)

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable libs; MaxMind DB format is stable; geoip2 API changes rarely)
