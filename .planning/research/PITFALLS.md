# Domain Pitfalls

**Domain:** Python network monitoring — Scapy + psutil + FastAPI + real-time web dashboard on Windows
**Researched:** 2026-03-31
**Confidence:** HIGH (stack-specific knowledge from training data, corroborated against known documentation patterns)

---

## Critical Pitfalls

Mistakes that cause rewrites, hangs, silent data loss, or fundamental design breakdowns.

---

### Pitfall 1: Scapy sniff() Blocks the Entire Python Thread

**What goes wrong:** `scapy.sniff()` is a synchronous, blocking call. If you call it from inside a FastAPI startup event, an async route, or the main thread of uvicorn, it blocks the entire process. No REST endpoints respond, no WebSocket frames are sent, and the application appears frozen.

**Why it happens:** Developers assume that because FastAPI is async, background tasks will run alongside it. They don't. `sniff()` holds the GIL-friendly C extension loop. `asyncio.run_in_executor` with the default thread pool also fails if the sniffer runs indefinitely, because the executor can't be cleanly shut down.

**Consequences:** The app starts but all HTTP traffic times out. The WebSocket never sends data. On SIGINT (Ctrl+C), the process may hang rather than exit cleanly.

**Prevention:**
- Run `sniff()` in a dedicated `threading.Thread(daemon=True)` started at application startup, separate from the uvicorn event loop.
- Use `sniff(prn=callback, store=False, stop_filter=stop_fn)` — `store=False` prevents accumulation of all packets in memory; `stop_filter` enables clean shutdown.
- Pass packets from the sniffer thread to the async world via `asyncio.Queue` and `loop.call_soon_threadsafe()` or via a `queue.Queue` polled by an async task using `asyncio.get_event_loop().run_in_executor`.
- Never call `sniff()` inside `async def` or any FastAPI lifecycle hook directly.

**Warning signs:** Starting the app and finding REST endpoints unresponsive. FastAPI startup logs appear but no requests are served.

**Phase:** Packet capture phase (Phase 1). Get the threading model right before adding any other layer.

---

### Pitfall 2: Npcap Not Installed — Silent or Cryptic Failures on Windows

**What goes wrong:** Scapy on Windows requires a packet capture driver: Npcap (current, actively maintained) or WinPcap (legacy, unmaintained since 2013). Without it, `sniff()` raises a cryptic error or silently captures nothing. WinPcap is incompatible with Windows 10/11 in many configurations and is no longer distributed.

**Why it happens:** `pip install scapy` succeeds, so developers assume the environment is ready. The missing driver is an OS-level dependency invisible to pip.

**Consequences:** `sniff()` raises `OSError: [Errno 22] Invalid argument` or similar low-level errors. On some systems, it raises `Scapy Runtime Error: No libpcap provider available`. The error message is non-obvious and hard to diagnose for first-time users.

**Prevention:**
- Document Npcap as a hard prerequisite in `README.md` and `requirements.txt` comments.
- Install Npcap from https://npcap.com with the "WinPcap API-compatible mode" option checked.
- Add a startup check: attempt to list interfaces with `scapy.arch.windows.get_windows_if_list()` and fail fast with a clear error message if Npcap is absent.
- Do NOT install both Npcap and WinPcap simultaneously — they conflict.
- Npcap also requires elevated privileges (Administrator) to install; document this in setup steps.

**Warning signs:** `sniff()` exits immediately with no packets captured, or raises `OSError` on the first call. `scapy.all.show_interfaces()` returns an empty list.

**Phase:** Phase 1 (packet capture). Verify the driver before writing any other code. Put a startup check in `sniffer.py`.

---

### Pitfall 3: Scapy Captures Only Loopback or Wrong Interface on Windows

**What goes wrong:** On Windows with multiple network adapters (Wi-Fi, Ethernet, VPN, WSL virtual adapter, Hyper-V adapter), Scapy may default to the wrong interface. Traffic appears to not be captured even though the sniffer is running.

**Why it happens:** Windows interface names differ from POSIX names (e.g., `\Device\NPF_{GUID}` instead of `eth0`). Scapy's auto-detection may select an inactive or virtual adapter.

**Consequences:** The sniffer runs silently with zero packets, or captures only loopback traffic that never reaches external IP addresses.

**Prevention:**
- Explicitly enumerate interfaces at startup using `scapy.arch.windows.get_windows_if_list()` and log them.
- Allow the user (or configuration) to specify the interface. Fall back to the interface with a default gateway.
- Filter out virtual adapters (Hyper-V, WSL) by checking the interface description string.
- Use `conf.iface` to set the default interface explicitly.

**Warning signs:** Sniffer reports running but no packets appear in the connection table. `scapy.all.get_if_list()` returns many entries including GUIDs.

**Phase:** Phase 1 (packet capture). Interface selection must be validated before moving to process mapping.

---

### Pitfall 4: psutil PID-to-Packet Correlation Race Condition

**What goes wrong:** `psutil.net_connections()` returns the current state of the connection table at a point in time. Scapy captures packets asynchronously. By the time the sniffer callback fires and calls `psutil.net_connections()`, short-lived connections may already be closed and the PID is gone. The result is a `None` PID for many connections, especially UDP DNS queries and brief TCP SYNs.

**Why it happens:** Scapy's packet callback fires after the kernel has already delivered the packet. DNS over UDP typically completes in milliseconds — well before the callback runs. The connection entry in the OS table is already removed.

**Consequences:** Many connections (especially DNS, QUIC, streaming) show `Unknown` process. Detection rule 4 ("unknown process = ALERT") fires constantly, producing alert noise that makes the tool appear broken.

**Prevention:**
- Cache the psutil connection table periodically in a background thread (e.g., every 200–500ms) and use the cached snapshot in the packet callback. This avoids calling `psutil.net_connections()` on every packet, which is expensive.
- Store the most recent PID for each `(src_ip, src_port, dst_ip, dst_port)` 4-tuple with a TTL. Reuse the cached PID for subsequent packets on the same connection.
- On Windows, `psutil.net_connections(kind='inet')` is significantly slower than on Linux — it calls `GetTcpTable2` and `GetUdpTable2` which iterate the full kernel table. Never call it synchronously inside the sniffer callback.
- Accept that UDP connections (DNS) will frequently have no PID and handle `None` gracefully everywhere downstream.

**Warning signs:** Most connections showing `Unknown` process. CPU spike when traffic is high (psutil being called per-packet). Alert panel flooded with "Unknown process" alerts.

**Phase:** Phase 2 (process mapping). Cache architecture must be designed here, not retrofitted later.

---

### Pitfall 5: DNS Reverse Lookup Blocks the Pipeline

**What goes wrong:** `socket.gethostbyaddr(ip)` is a blocking system call. It performs a real DNS query. On a busy network with many unique destination IPs, calling it synchronously blocks the packet processing pipeline. Under moderate traffic, this causes a packet processing backlog. Under heavy traffic (e.g., a video stream), the in-memory queue fills up and packets are dropped.

**Why it happens:** DNS reverse lookups (PTR queries) can take 1–5 seconds on IPs with no PTR record (which is most cloud CDN IPs). Many internet IPs have no reverse DNS entry. `socket.gethostbyaddr()` does not respect a short timeout by default.

**Consequences:** The sniffer callback or the processing queue stalls. The UI shows stale data. On Windows, a hung DNS call can block for the default system DNS timeout (15–30 seconds for NXDOMAIN with retry).

**Prevention:**
- Run DNS resolution in a separate thread pool (`concurrent.futures.ThreadPoolExecutor`) completely detached from the packet capture loop.
- Cache all resolved IPs with an in-memory dict. Never re-resolve an IP that was already looked up (even if the result was `None`).
- Set a hard timeout: use `socket.setdefaulttimeout(2.0)` or wrap the call to limit to 2 seconds. Return `None` immediately after timeout.
- Fall back gracefully: if no PTR record, display the raw IP. Do not mark this as suspicious by default.
- Consider caching negative results (no PTR record) to avoid repeated failed lookups.

**Warning signs:** Dashboard updates slow down over time as more unique IPs accumulate. CPU shows threads blocked on DNS. `socket.gethostbyaddr` appears in thread stack traces.

**Phase:** Phase 3 (DNS resolution). The cache and thread-pool design must be established here.

---

### Pitfall 6: Scapy Memory Leak from store=True (Default)

**What goes wrong:** `scapy.sniff()` defaults to `store=True`, which accumulates every captured packet in memory in a `PacketList`. On a busy network interface, this fills RAM in minutes and causes the process to be killed by the OS.

**Why it happens:** The `store=True` default is appropriate for interactive Scapy sessions where you want to inspect captured packets later. It is destructive for a long-running daemon.

**Consequences:** Memory grows linearly with captured traffic volume. After minutes to hours, the Python process is killed (OOM). The dashboard stops updating with no clear error.

**Prevention:** Always call `sniff(store=False, prn=callback)`. The `prn` callback processes each packet immediately and the packet object is discarded.

**Warning signs:** RAM usage grows continuously. Task Manager shows the Python process consuming increasing memory over time.

**Phase:** Phase 1. This is a one-line fix but must be known before writing the sniffer.

---

### Pitfall 7: In-Memory Connection List Grows Without Bound

**What goes wrong:** The `data_store.py` accumulates connection records in a Python list or dict. Over hours of monitoring, this grows to tens of thousands of entries. REST endpoint responses become multi-megabyte JSON payloads. The `/connections` endpoint becomes unusably slow.

**Why it happens:** The initial implementation stores all connections without a cap, because the volume during development testing is low. The problem only manifests after extended runtime.

**Consequences:** `GET /connections` eventually returns megabytes of JSON. The browser tab freezes rendering the table. The Python process runs out of memory. JSON log files grow without bound.

**Prevention:**
- Cap the in-memory connection list to a rolling window (e.g., last 1,000 connections using `collections.deque(maxlen=1000)`).
- Paginate the `/connections` REST endpoint from day one. Return at most 100 records per page.
- Rotate JSON log files by size or time (e.g., new file every 10MB or every hour).
- For the WebSocket, push only new/changed records (delta updates), not the full connection list on every push.

**Warning signs:** Memory growing slowly over hours. `/connections` response time increasing. JSON log files in `/logs/` exceeding 100MB.

**Phase:** Phase 5 (backend API). The data store design must account for growth before the API layer is built.

---

## Moderate Pitfalls

---

### Pitfall 8: WebSocket Broadcast Saturates the Event Loop Under Traffic Bursts

**What goes wrong:** When a download or video stream causes hundreds of packets per second, the sniffer thread pushes hundreds of WebSocket messages per second. The FastAPI/uvicorn event loop spends all its time broadcasting, REST endpoints become unresponsive, and the browser WebSocket client may drop frames.

**Why it happens:** Each packet potentially triggers a WebSocket broadcast. The handler is `O(n_connections * n_packets)` if broadcasting to multiple clients.

**Prevention:**
- Implement rate-limiting on WebSocket pushes: batch updates and push at a fixed interval (e.g., every 500ms), not per-packet.
- Use a dedicated asyncio task that reads from an internal queue and pushes batched updates. The sniffer thread puts raw data in the queue; the async task drains it on a timer.
- Throttle to a maximum of 2 broadcasts per second per WebSocket connection.

**Warning signs:** REST endpoints time out during active downloads. Browser console shows WebSocket errors or dropped frames. CPU at 100% on the uvicorn worker.

**Phase:** Phase 6 (frontend/WebSocket). Design the batching strategy when implementing the WebSocket handler, not after.

---

### Pitfall 9: Windows UAC / Administrator Privilege Handling

**What goes wrong:** The app requires Administrator privileges (for raw socket access via Npcap). Running without them causes `sniff()` to fail with a permission error. However, if the user just double-clicks `main.py` or runs `uvicorn` without elevation, the error message is buried in logs and the dashboard loads but shows no data.

**Why it happens:** The privilege check happens deep inside Scapy, not at startup. The FastAPI app itself starts successfully without admin rights; only the sniffer fails.

**Prevention:**
- Add an explicit privilege check at the top of `sniffer.py` using `ctypes.windll.shell32.IsUserAnAdmin()` on Windows.
- Fail fast with a clear error message if not elevated: `ERROR: This tool requires Administrator privileges. Please run as Administrator.`
- Document the requirement prominently in `README.md` and in the dashboard itself (show a banner if the backend reports insufficient privileges).

**Warning signs:** Dashboard loads but connection table stays empty. No error in the browser, but Python logs show a permissions error.

**Phase:** Phase 1. Add the check in the very first version of `sniffer.py`.

---

### Pitfall 10: Detection Rule 3 (Non-Standard Port) Generates Excessive Noise

**What goes wrong:** The detection rule `port NOT IN [80, 443, 53]` flags virtually all modern traffic. DNS over HTTPS uses port 443. Chrome uses QUIC on UDP port 443. Windows Update uses port 443. NTP uses UDP port 123. Many apps use ephemeral destination ports (e.g., online gaming, VoIP). The alerts panel fills with false positives immediately.

**Why it happens:** The allowlist is too narrow. Modern internet traffic is heavily concentrated on 443 but also legitimately uses many other ports.

**Prevention:**
- Expand the baseline allowlist: `[53, 80, 123, 443, 5353]` at minimum.
- Consider flagging only truly unusual destination ports (well below 1024 excluding the allowed set, or known-malicious ports) rather than anything outside a short list.
- Weight alerts by combination of signals (unknown process AND unusual port) rather than each signal independently.
- Add a confidence score to alerts rather than binary ALERT/WARNING.

**Warning signs:** Alerts panel full immediately on startup before any suspicious activity.

**Phase:** Phase 4 (detection engine). Tune rules with real traffic before considering them complete.

---

### Pitfall 11: Windows Firewall and VPN Adapters Capture Encrypted/Tunneled Traffic Only

**What goes wrong:** When a VPN is active, all traffic exits through the VPN tunnel adapter. Scapy captures packets on the physical interface but sees only encrypted VPN tunnel packets, not the actual application-level connections. Process mapping becomes impossible for tunneled traffic. The dashboard appears to show very little traffic when the VPN is on.

**Why it happens:** The VPN driver intercepts packets before they reach the physical layer that Scapy monitors.

**Prevention:**
- Document this known limitation. Do not attempt to decrypt VPN traffic.
- If capturing on the VPN adapter (e.g., `tap0` or `tun0`), packets may be visible but the destination IPs will be internal VPN IPs, not actual internet destinations.
- Detect when a VPN adapter is active and show a warning in the dashboard.

**Phase:** Phase 1. Document as a known limitation in `README.md` from the start.

---

### Pitfall 12: psutil.net_connections() Requires SYSTEM or Admin on Windows

**What goes wrong:** On Windows, `psutil.net_connections()` without elevated privileges returns connections but with `pid=None` for connections owned by processes the current user cannot inspect. System processes (LSASS, svchost, services) will always show `pid=None` without admin rights.

**Why it happens:** Windows process inspection (`OpenProcess`) requires `PROCESS_QUERY_INFORMATION` access, which is only granted for processes owned by the current user or for administrators.

**Prevention:** Run the entire tool as Administrator (already required for Npcap). The single admin privilege requirement covers both Scapy and psutil. Do not attempt to run with reduced privileges as a "safety" measure — it breaks process mapping silently.

**Warning signs:** Many connections showing `pid=None` even though the app starts without obvious errors.

**Phase:** Phase 2 (process mapping). Confirm admin mode is working before building the mapping logic.

---

## Minor Pitfalls

---

### Pitfall 13: JSON Log File Corruption on Unclean Shutdown

**What goes wrong:** If the app is killed mid-write to a JSON log file, the file ends in a partial JSON object. On next startup, attempting to read the log raises a `json.JSONDecodeError`.

**Prevention:** Write logs using JSON Lines format (one JSON object per line, newline-delimited) rather than a JSON array. Each write is atomic at the line level. Partial writes corrupt at most one line. Use `file.flush()` after each write.

**Phase:** Phase 5 (data store). Use JSON Lines from the start.

---

### Pitfall 14: Scapy IP Filter Captures Inbound Traffic Too

**What goes wrong:** `sniff(filter="ip")` captures all IP traffic: inbound, outbound, and broadcast. Routing everything through the processing pipeline doubles load and pollutes the connection table with inbound connections the user did not initiate.

**Prevention:** Filter to outbound connections at the BPF filter level: `sniff(filter="ip and (tcp or udp)")` combined with a Python-level check that `src_ip` matches the local machine's IP. Use `scapy.all.get_if_addr(iface)` to get the local IP and compare in the `prn` callback.

**Phase:** Phase 1. Set the correct filter on the first implementation.

---

### Pitfall 15: `socket.gethostbyaddr()` Returns Misleading CDN Hostnames

**What goes wrong:** Many IPs (Cloudflare, Fastly, Akamai, AWS CloudFront) return generic CDN PTR records like `server-1-2-3-4.ams50.r.cloudfront.net` rather than the actual service name. The dashboard shows these CDN hostnames instead of recognizable names like `netflix.com`.

**Prevention:** This is a fundamental DNS limitation — PTR records are not the same as forward DNS. Accept this as a known limitation. For phase-appropriate MVP, the raw PTR result is acceptable. A future enhancement could maintain a mapping of CIDR ranges to service names (e.g., AWS IP ranges JSON).

**Phase:** Phase 3 (DNS). Document as a known limitation, not a bug.

---

### Pitfall 16: Windows Defender / Antivirus Interferes with Npcap

**What goes wrong:** Windows Defender or third-party AV may flag Npcap's driver installation or quarantine the Npcap DLL. This causes `sniff()` to fail at runtime even when Npcap appears installed.

**Prevention:** Add Npcap installation directory (`C:\Windows\System32\Npcap\`) to AV exclusions during development. Document this in setup instructions.

**Phase:** Phase 1. Verify Npcap is not being blocked before attributing failures to code.

---

## Phase-Specific Warning Matrix

| Phase | Topic | Likely Pitfall | Mitigation |
|-------|-------|---------------|------------|
| Phase 1: Packet Capture | Npcap missing | Cryptic `OSError` with no packets | Startup check, clear error message |
| Phase 1: Packet Capture | Wrong network interface selected | Silent zero-packet capture | Enumerate interfaces, require explicit selection |
| Phase 1: Packet Capture | sniff() blocking FastAPI | App freezes | Run sniffer in daemon thread |
| Phase 1: Packet Capture | store=True default | RAM exhaustion over time | Always use `store=False` |
| Phase 1: Packet Capture | No admin check | Dashboard loads but shows nothing | Fail fast with `IsUserAnAdmin()` check |
| Phase 2: Process Mapping | psutil race condition on short-lived connections | Most connections show Unknown | Cache connection table every 200ms |
| Phase 2: Process Mapping | psutil called per-packet | CPU spike under traffic | Cache + TTL, not per-packet lookup |
| Phase 3: DNS Resolution | gethostbyaddr() blocking | Pipeline stall, stale dashboard | Thread pool + 2s timeout + cache |
| Phase 3: DNS Resolution | CDN PTR records | Misleading hostnames | Document as limitation |
| Phase 4: Detection Engine | Rule 3 noise (port allowlist) | Alert panel flooded on startup | Expand allowlist, use multi-signal scoring |
| Phase 5: Backend API | Unbounded connection list | Memory growth, slow responses | deque(maxlen=1000), paginate REST |
| Phase 5: Backend API | JSON array log file corruption | json.JSONDecodeError on startup | JSON Lines format |
| Phase 6: Frontend/WebSocket | Per-packet broadcast | Event loop saturation, REST timeouts | Batch at 500ms interval |
| All Phases | VPN active | Encrypted tunnel, no process mapping | Document limitation, show warning |

---

## Sources

- Scapy documentation (https://scapy.readthedocs.io) — sniff() API, Windows installation, interface handling
- psutil documentation (https://psutil.readthedocs.io) — net_connections(), Windows privilege requirements, performance characteristics
- Python socket documentation — gethostbyaddr() blocking behavior, timeout handling
- FastAPI documentation (https://fastapi.tiangolo.com) — WebSocket, background tasks, startup events
- Npcap project (https://npcap.com) — Windows packet capture driver, WinPcap incompatibility
- Windows API documentation — GetTcpTable2, IsUserAnAdmin, process privilege model
- Knowledge basis: HIGH confidence on threading/blocking issues (well-documented Python behavior); HIGH confidence on Npcap dependency (standard Windows Scapy requirement); HIGH confidence on psutil race conditions (inherent to the architecture); MEDIUM confidence on exact DNS timeout values (OS-dependent, verify empirically).
