---
phase: 3
slug: enrichment-service
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pytest.ini` (exists — `asyncio_mode = auto`) |
| **Quick run command** | `python -m pytest tests/test_pipeline/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_pipeline/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green (39 existing + Phase 3 new tests)
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 0 | DNS-01..06 | unit | `pytest tests/test_pipeline/test_dns_resolver.py -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | DNS-01 | unit | `pytest tests/test_pipeline/test_dns_resolver.py::test_resolves_known_ip -x` | ✅ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | DNS-02 | unit | `pytest tests/test_pipeline/test_dns_resolver.py::test_dns_uses_executor -x` | ✅ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | DNS-03 | unit | `pytest tests/test_pipeline/test_dns_resolver.py::test_timeout_fires -x` | ✅ W0 | ⬜ pending |
| 03-01-05 | 01 | 1 | DNS-04 | unit | `pytest tests/test_pipeline/test_dns_resolver.py::test_cache_hit -x` | ✅ W0 | ⬜ pending |
| 03-01-06 | 01 | 1 | DNS-05 | unit | `pytest tests/test_pipeline/test_dns_resolver.py::test_no_ptr_fallback -x` | ✅ W0 | ⬜ pending |
| 03-01-07 | 01 | 1 | DNS-06 | unit | `pytest tests/test_pipeline/test_dns_resolver.py::test_cache_lru_eviction -x` | ✅ W0 | ⬜ pending |
| 03-02-01 | 02 | 0 | GEO-01..05 | unit | `pytest tests/test_pipeline/test_geo_enricher.py -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | GEO-01 | unit | `pytest tests/test_pipeline/test_geo_enricher.py::test_country_lookup -x` | ✅ W0 | ⬜ pending |
| 03-02-03 | 02 | 1 | GEO-02 | unit | `pytest tests/test_pipeline/test_geo_enricher.py::test_asn_lookup -x` | ✅ W0 | ⬜ pending |
| 03-02-04 | 02 | 1 | GEO-03 | unit | `pytest tests/test_pipeline/test_geo_enricher.py::test_geo_latency -x` | ✅ W0 | ⬜ pending |
| 03-02-05 | 02 | 1 | GEO-04 | unit | `pytest tests/test_pipeline/test_geo_enricher.py::test_address_not_found -x` | ✅ W0 | ⬜ pending |
| 03-02-06 | 02 | 1 | GEO-05 | unit | `pytest tests/test_pipeline/test_geo_enricher.py::test_stale_warning -x` | ✅ W0 | ⬜ pending |
| 03-03-01 | 03 | 0 | THREAT-01..05 | unit | `pytest tests/test_pipeline/test_threat_intel.py -x` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 1 | THREAT-01 | unit | `pytest tests/test_pipeline/test_threat_intel.py::test_blocklisted_ip -x` | ✅ W0 | ⬜ pending |
| 03-03-03 | 03 | 1 | THREAT-02 | unit | `pytest tests/test_pipeline/test_threat_intel.py::test_missing_file -x` | ✅ W0 | ⬜ pending |
| 03-03-04 | 03 | 1 | THREAT-03 | unit | `pytest tests/test_pipeline/test_threat_intel.py::test_lookup_latency -x` | ✅ W0 | ⬜ pending |
| 03-03-05 | 03 | 1 | THREAT-04 | unit | `pytest tests/test_pipeline/test_threat_intel.py::test_stale_warning -x` | ✅ W0 | ⬜ pending |
| 03-03-06 | 03 | 1 | THREAT-05 | unit | `pytest tests/test_pipeline/test_threat_intel.py::test_flag_fields -x` | ✅ W0 | ⬜ pending |
| 03-03-07 | 03 | 1 | SYS-03 | unit | `pytest tests/test_pipeline/test_worker.py::test_probe_fallback_logged -x` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline/test_dns_resolver.py` — stubs for DNS-01 to DNS-06 (6 test functions, all fail initially)
- [ ] `tests/test_pipeline/test_geo_enricher.py` — stubs for GEO-01 to GEO-05 (5 test functions, all fail initially)
- [ ] `tests/test_pipeline/test_threat_intel.py` — stubs for THREAT-01 to THREAT-05 (5 test functions, all fail initially)

**Mock requirements for Wave 0 stubs:**
- `geoip2.database.Reader` must be mocked in all GeoIP tests — MMDB files not present in CI. Use `unittest.mock.patch` on `geoip2.database.Reader`.
- `socket.gethostbyaddr` must be mocked in all DNS tests — avoids actual network calls and 2-second delays.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GeoLite2 DB download & load | GEO-01, GEO-02 | Requires MaxMind account / license key; MMDB file not in repo | 1. Register at maxmind.com. 2. Download GeoLite2-Country.mmdb + GeoLite2-ASN.mmdb to `data/`. 3. Run `python -m pytest tests/test_pipeline/test_geo_enricher.py -x -q` with MMDB files present. |
| DNS resolution of real IPs | DNS-01, DNS-05 | Requires live network + real PTR records | 1. Start backend with admin. 2. curl localhost:8000/api/v1/events. 3. Verify `dns.hostname` populated for known IPs, raw IP for no-PTR IPs. |
| End-to-end pipeline enrichment | SYS-03 | Requires full stack + Npcap + real traffic | 1. Start backend. 2. Browse to any HTTPS site. 3. Check WebSocket feed for country, asn, is_blocklisted fields. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
