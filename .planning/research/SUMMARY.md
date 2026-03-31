# Research Summary: Personal Network Privacy Guardian (PNPG)

**Domain:** Local network privacy monitoring tool — packet capture, process attribution, anomaly detection, real-time web dashboard
**Researched:** 2026-03-31
**Overall confidence:** HIGH (core stack is stable, well-documented Python ecosystem; Windows-specific Npcap requirement is well-established)
**Research note:** External network tools were unavailable during this session. Findings are drawn from training data (knowledge cutoff August 2025) and corroborated across four parallel research files. PyPI version numbers carry MEDIUM confidence and should be validated at install time.

---

## Executive Summary

The PNPG stack chosen in the PRD is technically sound and well-calibrated for an academic lab project. Python 3.11+ with Scapy, psutil, FastAPI, uvicorn, and a vanilla JS + Chart.js frontend is the correct combination for this problem domain in 2025. There are no major stack substitutions to recommend — the existing choices are the de facto standard for this class of tool.

The primary technical risk is not stack selection but architectural execution. Scapy's `sniff()` is blocking and must run in a dedicated daemon thread; `socket.gethostbyaddr()` is blocking and must run via `run_in_executor`; and `psutil.net_connections()` is synchronous and expensive enough to require a polling cache rather than per-packet calls. Getting all three threading concerns right in Phase 1 is the single most important implementation decision in the project. Retrofitting this architecture after other layers are built is significantly harder than establishing it from the beginning.

The Windows platform introduces three hard prerequisites not visible to pip: Npcap (the WinPcap replacement required for raw packet capture), Administrator elevation (required for both Scapy raw sockets and psutil PID access), and explicit network interface selection (Windows uses GUID-based interface names, not eth0/wlan0). All three must be validated with startup checks before any other code runs.

The PRD is well-scoped. All identified table-stakes features are present, the out-of-scope list is correct, and the build order (packet capture → process mapping → DNS → detection → API → frontend) reflects the true dependency chain. There are four minor gaps (capture status indicator, graceful shutdown, detection rule noise from the port allowlist, and NDJSON vs single JSON array logging) that are low complexity to address and worth including.

---

## Key Findings

**Stack:** Python 3.11+ / Scapy + Npcap (Windows) / psutil / socket (threaded) / FastAPI 0.110+ / uvicorn[standard] / Vanilla JS + Chart.js 4.x — all PRD choices are correct, validated against current best practices.

**Architecture:** Pipeline pattern with a strict unidirectional data flow: sniffer daemon thread → asyncio queue → pipeline worker coroutine → data store → WebSocket broadcast. The threading bridge between Scapy's blocking world and FastAPI's async world is the architectural core.

**Critical pitfall:** The blocking nature of three separate calls — `sniff()`, `gethostbyaddr()`, and `net_connections()` — must each be handled with dedicated threading or executor strategies. Running any of these on the asyncio event loop will freeze the application.

---

## Implications for Roadmap

Based on research across all five files, the recommended phase structure is:

1. **Phase 1 — Packet Capture Foundation** - Establish the threading architecture before adding any other layer. Verify Npcap, admin elevation, interface selection, and the thread-safe queue bridge. Use `sniff(store=False, prn=callback)`. All subsequent phases are blocked on this working correctly.
   - Addresses: Scapy capture, threading model, Windows prerequisites
   - Avoids: Sniffer blocking FastAPI, Npcap missing (silent failure), wrong interface (silent zero-packet capture)

2. **Phase 2 — Process Attribution** - Add `psutil.net_connections()` correlation with a proactive polling cache (200ms interval). Never call psutil per-packet. Mark unmapped connections as "unknown process" rather than failing.
   - Addresses: Process mapping to PIDs/process names
   - Avoids: psutil race condition on short-lived connections, per-packet psutil CPU spike

3. **Phase 3 — DNS Resolution** - Implement reverse DNS lookup in a thread pool with a TTL cache and 2-second timeout. Cache negative results (no PTR record). Fall back to raw IP gracefully.
   - Addresses: IP-to-domain resolution
   - Avoids: gethostbyaddr() blocking the pipeline, repeated lookups for the same IPs

4. **Phase 4 — Detection Engine** - Implement 4 rule set with expanded port allowlist (add 123, 5353, 8080, 8443). Use named constants for thresholds, not magic numbers. Tune rules with real traffic before marking complete.
   - Addresses: Anomaly detection, alert generation
   - Avoids: Port-allowlist rule flooding the alert panel with false positives on startup

5. **Phase 5 — Data Store + Backend API** - Use `collections.deque(maxlen=1000)` for in-memory store. NDJSON format for log files (not a single JSON array — corruption-safe). FastAPI with lifespan context manager (not deprecated `on_event`). Use `uvicorn[standard]` to pull in websockets dependency.
   - Addresses: REST endpoints, persistent logging, data management
   - Avoids: Unbounded memory growth, JSON log corruption on unclean shutdown

6. **Phase 6 — Frontend Dashboard** - WebSocket client with batched UI updates (do not re-render on every packet). Chart.js 4.x (not 3.x — breaking changes). Bootstrap 5 CDN for table/alert styling. Native browser WebSocket API, no socket.io needed.
   - Addresses: Live connections table, alerts panel, two charts
   - Avoids: Per-packet DOM re-render, Chart.js version mismatch

**Phase ordering rationale:**
- Phases 1-4 can be developed and tested with Python scripts alone, no FastAPI needed. This is the correct approach — validate the data pipeline before building the API that exposes it.
- Phase 2 (process mapping) and Phase 3 (DNS) are independent of each other and can proceed in parallel; they converge in Phase 4 where the detection engine needs both process name and domain name.
- The API (Phase 5) is glue — it must not be built before the pipeline it exposes is working correctly. Building the API first creates a seductive but empty shell.
- The frontend (Phase 6) has zero implementation risk once the WebSocket message contract is stable; save it for last.

**Research flags for phases:**
- Phase 1: Needs empirical validation of Npcap + Windows interface selection behavior on the target machine. Network driver behavior is environment-dependent.
- Phase 3: DNS timeout values are OS-dependent. The 2-second recommendation needs empirical tuning on the target machine.
- Phase 4: Detection rule thresholds (connections-per-second) need calibration against real baseline traffic. What constitutes "high rate" varies by machine and usage pattern.
- Phases 2, 5, 6: Standard patterns with HIGH confidence; unlikely to need additional research.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack choices | HIGH | All PRD choices validated as current best practices for this problem domain |
| Library versions | MEDIUM | Cited from training data (cutoff August 2025); validate against PyPI before pinning |
| Windows prerequisites (Npcap) | HIGH | Hard requirement, well-documented, has been true since Scapy 2.4.x |
| Threading/async architecture | HIGH | Python threading + asyncio bridge is stable, well-documented behavior |
| psutil Windows behavior | MEDIUM | Core behavior is HIGH; AccessDenied edge cases with specific system processes need empirical testing |
| Detection rule tuning | LOW | Threshold values need empirical calibration against real traffic on the target machine |
| Chart.js 4 breaking changes | HIGH | Well-documented, stable since 2022 release |
| DNS timeout behavior | MEDIUM | OS-dependent; 2-second recommendation is reasonable but needs empirical validation |

---

## Gaps to Address

1. **Npcap version compatibility**: Confirm the current Npcap version works cleanly with the current Scapy release on Windows 11 Home (the stated target). This is environment-specific.

2. **Detection threshold baselines**: The `connections_per_second` threshold for rule 2 has no validated value. It needs calibration: run the tool against normal baseline traffic and observe the rate before setting a threshold. A hardcoded value of 50/second is a starting guess, not a validated baseline.

3. **Interface auto-selection on multi-adapter Windows machines**: The target machine (Windows 11 Home) likely has Wi-Fi + VPN adapters. The auto-selection logic for the correct physical interface needs to be tested on the actual hardware, not assumed.

4. **WebSocket batching interval**: The 500ms batching recommendation for UI updates is a reasonable default but has not been tested against actual Chart.js rendering performance in a browser. If Chart.js 4.x update cost is high, this interval may need adjustment.

5. **psutil version API**: psutil 5.9.x vs 6.x may have changed `net_connections()` parameters. Validate the method signature against the installed version.

---

## Files in This Research Directory

| File | Coverage |
|------|---------|
| `STACK.md` | Technology recommendations with versions, Windows-specific notes, PRD validation |
| `FEATURES.md` | Feature landscape, comparable tools analysis, MVP scope assessment |
| `ARCHITECTURE.md` | Threading model, pipeline architecture, component boundaries, anti-patterns |
| `PITFALLS.md` | 16 pitfalls across all phases, Windows-specific failure modes, phase-warning matrix |
| `SUMMARY.md` | This file — executive summary, roadmap implications, confidence assessment |
