# Phase 2: Process Attribution - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 02-process-attribution
**Areas discussed:** Packet field extraction

---

## Packet Field Extraction

### Gray area selection

| Area | Selected |
|------|----------|
| Packet field extraction | ✓ |
| Event schema after attribution | |
| Cache TTL expiry mechanism | |
| Poller lifecycle & placement | |

### Q1: Where should src_ip, src_port, dst_ip, dst_port, protocol be extracted?

| Option | Description | Selected |
|--------|-------------|----------|
| In the queue bridge | Enrich event at capture time in queue_bridge.py — raw_pkt becomes fields immediately. Downstream never touches Scapy. | ✓ |
| In the process mapper (Phase 2 stage) | Phase 2 extracts what it needs; later phases extract their own fields | |
| Dedicated extraction stage before Phase 2 | New pipeline stage (pnpg/capture/extractor.py) converts raw_pkt → flat dict | |

**User's choice:** In the queue bridge (Recommended)
**Notes:** None

---

### Q2: After extracting fields, keep raw_pkt in the event or drop it?

| Option | Description | Selected |
|--------|-------------|----------|
| Drop it | Event carries only flat extracted fields. Smaller events, no Scapy dependency downstream. | |
| Keep it for debug mode | raw_pkt stays in dict only when config debug_mode=True. Useful for troubleshooting. | ✓ |

**User's choice:** Keep it for debug mode
**Notes:** None

---

### Q3: What happens when a packet has no TCP/UDP layer (ICMP, fragmented)?

| Option | Description | Selected |
|--------|-------------|----------|
| Set ports to None, keep the event | src_port=None, dst_port=None, protocol from IP header. Event flows normally; process mapper cache miss → "unknown process". | ✓ |
| Drop the event silently | Non-TCP/UDP packets discarded at the bridge. | |
| Drop with INFO log | Same as silent drop, but logs each non-TCP/UDP drop. | |

**User's choice:** Set ports to None, keep the event (Recommended)
**Notes:** None

---

### Ready to write context

User selected "Ready to write context" — three decisions were sufficient for the planner.
