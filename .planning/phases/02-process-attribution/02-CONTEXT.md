# Phase 2: Process Attribution - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Enrich every packet event in the pipeline with the originating process name and PID using a proactive psutil polling cache (200ms background schedule). Unattributable connections degrade gracefully to "unknown process" / PID -1. No UI, no persistence, no DNS — pure data enrichment of the pipeline event schema.

</domain>

<decisions>
## Implementation Decisions

### Packet Field Extraction

- **D-01:** Extract `src_ip`, `src_port`, `dst_ip`, `dst_port`, and `protocol` **in the queue bridge** (`make_packet_event()` in `pnpg/capture/queue_bridge.py`), not in the process mapper or a separate stage. All downstream phases (Phase 2 process mapping, Phase 3 DNS, Phase 4 detection, Phase 5 storage) receive clean flat dicts and never need to import or parse Scapy directly.
- **D-02:** Keep `raw_pkt` in the event dict only when `config["debug_mode"] == True`. Drop it otherwise. This keeps per-event memory low in production while preserving debug capability.
- **D-03:** When a packet has no TCP/UDP layer (ICMP, fragmented, etc.): set `src_port = None` and `dst_port = None`, keep the event flowing. `protocol` is still extracted from the IP header (e.g., ICMP = 1). The process mapper will get a cache miss on `(src_ip, None)` and degrade to "unknown process" naturally — no special case needed.

### Resulting Event Schema (after Phase 2)

After `make_packet_event()` is updated and process attribution is applied, every pipeline event will carry:

```python
{
    "timestamp": "<ISO8601 UTC str>",     # CAP-08
    "monotonic": <float>,                  # CAP-08
    "src_ip":    "<str>",                  # D-01
    "src_port":  <int | None>,             # D-01 / D-03
    "dst_ip":    "<str>",                  # D-01
    "dst_port":  <int | None>,             # D-01 / D-03
    "protocol":  <int>,                    # D-01 (IP proto number: TCP=6, UDP=17, etc.)
    "process_name": "<str>",               # PROC-01/03/04 ("unknown process" on failure)
    "pid":       <int>,                    # PROC-01/03 (-1 on failure)
    "raw_pkt":   <Scapy packet | absent>,  # D-02 (only if debug_mode=True)
}
```

This schema is the **data contract** for Phase 3 onwards. Downstream plans must not assume any additional fields.

### Claude's Discretion

- Cache data structure internals (dict vs OrderedDict vs custom), TTL expiry mechanism (lazy vs eager), and poller lifecycle placement (standalone task vs self-managing module) were not discussed — Claude has full discretion on these. Requirements PROC-02/05/06 specify *what* (200ms polling, (src_ip, src_port) key, 2s TTL), not *how*.
- The existing `ThreadPoolExecutor(max_workers=4)` in `pipeline_worker` may be reused for the per-event dict lookup if the executor is passed in, or a synchronous dict lookup in the async worker is acceptable (it's O(1) with no I/O).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 2 requirements
- `.planning/REQUIREMENTS.md` §Process Attribution — PROC-01 through PROC-06 (all Phase 2 requirements)

### Phase 1 foundation code
- `pnpg/capture/queue_bridge.py` — `make_packet_event()` must be modified per D-01/D-02/D-03
- `pnpg/pipeline/worker.py` — Phase 2 stub at line 48: `# Phase 2: event = await process_mapper(event, executor, loop)`
- `pnpg/main.py` — lifespan manages asyncio tasks; poller task should follow the same pattern as `sniffer_supervisor` and `pipeline_worker`
- `config.yaml` — TTL and poll interval should be added as named config keys (consistent with existing config pattern)

### Project constraints
- `CLAUDE.md` — stack constraints, Windows-specific notes, performance requirements (psutil 200ms max)

No external ADRs or third-party specs required — all constraints are in REQUIREMENTS.md and CLAUDE.md.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pnpg/capture/queue_bridge.py` — `make_packet_event()`: modify in-place to add field extraction (D-01/D-02/D-03). Already has `drop_counter` pattern for the mutable counter idiom.
- `pnpg/pipeline/worker.py` — `pipeline_worker()`: Phase 2 stub is at the right place. `ThreadPoolExecutor` already instantiated and available.
- `pnpg/main.py` — lifespan pattern: `asyncio.create_task(...)` already used for supervisor and worker — poller task fits the same pattern.
- `tests/conftest.py` — shared fixtures exist; the mock pattern for `_get_scapy_ifaces()` in `interface.py` shows how to isolate psutil calls for testing without a real network.

### Established Patterns
- **Immutable event dicts**: Events are plain dicts built in `make_packet_event()` and never mutated after — each enrichment stage should return a new dict via `{**event, "new_field": value}`.
- **Config from load_config()**: All tunable values come from `config.yaml` via `load_config()`. New keys (poll_interval_ms, proc_ttl_secs) follow the same DEFAULT_CONFIG pattern in `pnpg/config.py`.
- **Critical error logging without crash**: `except Exception: logger.critical(...)` in `pipeline_worker` — process attribution errors follow the same pattern.
- **daemon threads + asyncio tasks**: Phase 1 uses a daemon thread (Scapy) bridged to an asyncio task (supervisor). The psutil poller is a pure asyncio task (no thread needed — psutil.net_connections() is fast enough for 200ms polling).

### Integration Points
- `make_packet_event()` in `queue_bridge.py` is the single injection point for field extraction (D-01).
- The `pipeline_worker()` enrichment stub in `worker.py` is the injection point for process attribution.
- `main.py` lifespan is where the background poller task is started and cancelled on shutdown.
- `pnpg/config.py` `DEFAULT_CONFIG` is where `proc_poll_interval_ms: 200` and `proc_ttl_secs: 2` defaults should be added.

</code_context>

<specifics>
## Specific Ideas

No specific references or "I want it like X" moments — user selected recommended defaults throughout. Open to standard implementation approaches within the constraints above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-process-attribution*
*Context gathered: 2026-04-01*
