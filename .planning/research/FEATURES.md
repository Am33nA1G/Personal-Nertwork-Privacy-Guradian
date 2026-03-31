# Feature Landscape: Local Network Privacy Monitoring / Anomaly Detection

**Domain:** Local network privacy guardian / traffic visibility tool
**Researched:** 2026-03-31
**Research basis:** Training knowledge of production tools (Little Snitch, GlassWire, Wireshark, ntopng, Zeek, NetLimiter, Charles Proxy, Portmaster) + PRD cross-reference
**Confidence:** MEDIUM — WebSearch unavailable; domain knowledge is stable (features in this space don't shift rapidly)

---

## Comparable Tools in the Ecosystem

| Tool | Category | Target User | Key Differentiator |
|------|----------|-------------|-------------------|
| Little Snitch (macOS) | Privacy guardian | Non-expert consumer | Per-app firewall + approval dialogs |
| GlassWire (Windows) | Privacy/monitoring | Non-expert consumer | Beautiful timeline UI, anomaly alerts |
| Wireshark | Deep packet inspection | Network expert | Full packet capture, protocol decode |
| ntopng | Enterprise monitoring | IT/ops | Multi-host, flow-based, dashboards |
| Portmaster (open source) | Privacy guardian | Privacy-conscious user | DNS filtering, per-app rules |
| Charles Proxy | Debug proxy | Developer | HTTPS inspection, request replay |
| Zeek (formerly Bro) | Network security | Security analyst | Scripted behavioral analysis |
| NetLimiter | Bandwidth control | Power user | Per-app bandwidth throttling |

**PNPG sits closest to:** GlassWire + Portmaster, but academic/local-first and without a firewall component.

---

## Table Stakes

Features that users expect from ANY tool in this category. Missing one makes the tool feel broken or useless.

| Feature | Why Expected | Complexity | PRD Status | Notes |
|---------|--------------|------------|------------|-------|
| Real-time packet capture (outgoing) | Core capability — no capture = no tool | Medium | Included (Scapy) | Requires admin/root — this is expected |
| Per-app connection attribution | "Which app is doing this?" is the #1 user question | Medium | Included (psutil) | The psutil correlation approach is correct |
| IP-to-domain resolution (DNS reverse lookup) | Raw IPs are meaningless to users | Low | Included (socket) | Fallback to raw IP if no PTR record is correct |
| Live connections view (table/list) | Users need to see what's happening RIGHT NOW | Low | Included (dashboard) | Time, app, domain, IP, port, protocol — covered |
| Alert/anomaly notification panel | Users need to know when something looks wrong | Low | Included (alerts panel) | Even simple rule-based is sufficient at this scale |
| Persistent log of connections | Must be able to review what happened | Low | Included (JSON logs) | JSON flat files are sufficient for v1 |
| Basic protocol/port identification | TCP vs UDP, port 443 vs 8080 — minimum context | Low | Included (analyzer.py) | Standard filter set covers this |
| Graceful startup / shutdown | Must start/stop without leaving orphaned processes | Low | Not explicitly in PRD | Add to implementation checklist |
| Status indicator (is capture running?) | User must know if the tool is active | Low | Not explicitly in PRD | A simple "Capturing / Stopped" UI state is enough |

**Assessment:** PRD covers all core table stakes. Two minor gaps noted (graceful shutdown, capture status indicator) — both are low complexity to add.

---

## Differentiators

Features that are NOT expected by default but add real value — especially for an academic/lab demonstration context where the goal is to show breadth of networking knowledge and full-stack skill.

| Feature | Value Proposition | Complexity | PRD Status | Notes |
|---------|------------------|------------|------------|-------|
| Connections-per-second chart | Visual spike detection — makes anomalies obvious at a glance | Low | Included (Chart.js) | This is a strong differentiator for a demo |
| Per-app data usage chart | "Chrome used 500MB, this unknown process used 50MB" — privacy insight | Low | Included (Chart.js) | Good academic talking point |
| Rule-based anomaly detection with labeled categories | Moving beyond raw data into interpretation — "this is suspicious, here's why" | Medium | Included (4 rules) | The 4-rule set is a solid starting point |
| WebSocket real-time push (no polling) | Snappier than REST-polled dashboards; shows architecture sophistication | Medium | Included (FastAPI WS) | This alone distinguishes from naive implementations |
| Unknown process detection | Privacy-critical: something is talking to the internet and you don't know what it is | Low | Included (rule 4) | Especially impactful for demo scenarios |
| No external data sharing (fully local) | Privacy-by-design — tool doesn't itself phone home | Low | Included (design principle) | A key differentiator vs cloud-based monitoring tools |
| Unknown domain flagging (no PTR record) | Catches exfiltration to raw IPs — a real attack vector | Low | Included (rule 1) | Simple but effective |
| High-rate connection burst detection | Catches port scanners, malware C2, update storms | Low | Included (rule 2) | Threshold must be configurable or at least documented |
| Non-standard port flagging | Catches tunneling, C2 over unusual ports | Low | Included (rule 3) | The whitelist of [80, 443, 53] is a good starting assumption |
| Auto-generated REST API docs (OpenAPI/Swagger) | FastAPI generates these for free — shows the API surface professionally | Low | Implicit (FastAPI) | Worth explicitly demonstrating in the README |

**Assessment:** The PRD's differentiator set is well-chosen for an academic project. The combination of real-time WebSocket push + Chart.js visualizations + rule-based detection is exactly the right scope — enough complexity to be interesting, not so much that it becomes unmaintainable.

---

## Anti-Features

Things to deliberately NOT build. Each is a scope creep trap that adds significant complexity with low academic/demo value.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Firewall / connection blocking | Adds OS-level integration complexity (Windows Filtering Platform, iptables) that is a project unto itself. Out of scope for a monitoring tool. | Display the alert and let the user decide. Log it. |
| HTTPS/TLS traffic decryption (MITM proxy) | Requires installing a custom CA cert, breaking certificate pinning, and creating a real security risk. Enormous complexity. | Observe connection metadata (IP, port, domain, volume) — not payload |
| Threat intelligence feed integration (VirusTotal, AbuseIPDB) | Introduces external API dependencies, rate limiting, API keys, privacy leaks (IPs sent to third party). | Rule-based local detection is sufficient and more trustworthy for v1 |
| Multi-host / LAN-wide monitoring | Changes the architecture fundamentally. You're no longer monitoring one host — you need a network tap or managed switch. | Scope to the local machine only |
| Historical trend analysis / long-term storage | Requires a proper database, query layer, time-series indexing. JSON logs don't scale to 30-day history. | Keep JSON logs as ephemeral session logs; defer SQLite upgrade |
| User authentication / access control | Local tool. Single user. Adding auth adds login UX, session management, token storage — zero benefit here. | Run on localhost only, no auth needed |
| Mobile companion app | Cross-platform agent requires Kivy, React Native, or similar — completely separate project. | Browser dashboard running on localhost is sufficient |
| IPv6 deep inspection | IPv6 adds complexity to the correlation layer (psutil + Scapy both need separate handling). | Handle IPv4 first; IPv6 is a future extension |
| Packet payload inspection | GDPR/legal concerns, performance cost, and user privacy contradiction — a privacy tool that reads payload content is ironic. | Observe metadata only (IPs, ports, domains, volumes) |
| Cloud dashboard / remote access | Defeats the "runs locally, no external data sharing" privacy guarantee. | Localhost only — the design principle is the differentiator |

---

## Feature Dependencies

```
Packet capture (Scapy)
  └─ Connection extractor (analyzer.py)
       └─ Process mapper (psutil correlation)
            └─ DNS resolver (socket)
                 └─ Detection engine (4 rules)
                      └─ Data store (in-memory + JSON)
                           └─ FastAPI REST endpoints
                                └─ WebSocket push (/ws/live)
                                     └─ Frontend dashboard
                                          ├─ Live connections table
                                          ├─ Alerts panel
                                          └─ Charts (Chart.js)
```

This dependency chain is exactly the build order specified in the PRD (section 14). The order is correct — each layer depends on the one above it.

---

## MVP Recommendation

The PRD already describes a well-scoped MVP. Prioritize in this order:

1. **Packet capture + process attribution** — Without this, nothing else matters. Verify sniffing works and PID correlation is accurate before adding any other layer.
2. **DNS resolution + detection rules** — These are low complexity and transform raw connections into meaningful, actionable information.
3. **FastAPI + WebSocket backend** — Expose the data pipeline through the API surface.
4. **Frontend dashboard** — Connections table + alerts panel are highest priority; charts are secondary.
5. **JSON logging** — Add after the pipeline is proven; logging is not needed to demonstrate the core capability.

**Defer with explicit rationale:**
- SQLite upgrade: JSON logs are sufficient for a demo session; upgrade only if persistent history across restarts becomes a requirement
- Configurable rule thresholds: Hard-code sensible defaults for v1; make them constants (not magic numbers) so they're easy to tune
- Bootstrap: Optional per PRD — use only if vanilla CSS slows down frontend work

---

## PRD Feature Set Evaluation

### Completeness Assessment

| PRD Feature | Category | Status |
|-------------|----------|--------|
| Scapy packet capture | Table stakes | Complete — correct approach |
| psutil process mapping | Table stakes | Complete — known pitfall: psutil correlation has a race condition (connection closes before poll); mitigate with a short-lived connection cache |
| socket DNS resolution | Table stakes | Complete — fallback to raw IP correctly noted |
| Rule-based detection (4 rules) | Differentiator | Complete — good starting set; threshold for rule 2 needs a constant, not a magic number |
| FastAPI REST API | Differentiator (architecture) | Complete — 3 endpoints are sufficient |
| WebSocket /ws/live | Differentiator | Complete — correct choice over polling |
| Live connections table | Table stakes | Complete |
| Alerts panel | Table stakes | Complete |
| Chart.js charts (2 charts) | Differentiator | Complete — data usage + connections/second is the right pair |
| JSON log files | Table stakes | Complete |

### Gaps (minor, low complexity)

| Gap | Impact | Effort | Recommendation |
|-----|--------|--------|----------------|
| Capture status indicator (is sniffing running?) | User confusion if tool silently fails | Low | Add a `/health` or `/status` endpoint; show "Capturing" / "Stopped" in UI header |
| Graceful shutdown handling | Orphaned threads can hold sockets | Low | Register signal handlers (SIGINT, SIGTERM) to stop sniff loop cleanly |
| Threshold constant for rate detection | Magic numbers in detector.py are a maintenance risk | Low | Define `CONNECTIONS_PER_SECOND_THRESHOLD = 50` as a named constant |
| Port whitelist is too narrow | Port 8080, 8443, 853 (DNS-over-TLS) are legitimate | Low | Expand default whitelist slightly; flag anything truly unusual |

### Over-Engineering Risks

| Risk | Verdict |
|------|---------|
| SQLite included in PRD as "optional upgrade" | Correctly deferred. Do not touch for v1. |
| Bootstrap listed as optional | Correct. Vanilla CSS is fine; Bootstrap adds a dependency for marginal gain. |
| WebSocket chosen over REST polling | Correct for this use case — not over-engineering. Demonstrates real-time architecture. |

### Overall PRD Verdict

The PRD is well-scoped and correctly calibrated for an academic/lab project. The feature set hits all table stakes, includes meaningful differentiators, and the out-of-scope list correctly excludes the dangerous scope-creep traps. The 4 minor gaps above are all low-effort additions that improve polish without expanding scope.

---

## Sources

- Domain knowledge: GlassWire feature set (glasswire.com), Little Snitch documentation, Portmaster (safing.io) feature list, Wireshark wiki
- Confidence: MEDIUM — based on training knowledge through August 2025; WebSearch unavailable for live verification
- PRD analysis: Direct cross-reference against `PRD.md` and `PROJECT.md` in this repository
