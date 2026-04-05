---
status: complete
phase: 03-enrichment-service
source: [phase success criteria — no SUMMARY.md files]
started: 2026-04-05
updated: 2026-04-05
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server. Start the backend from scratch with `python -m uvicorn pnpg.main:app --reload`. Server boots without errors, all enrichment resources initialize (DNS cache created, GeoIP readers attempted, blocklist loaded), and startup logs show no exceptions.
result: blocked
blocked_by: prior-phase
reason: "Npcap not installed — check_npcap() calls sys.exit(1). Hard prerequisite gate from Phase 1."

### 2. DNS Resolution — Known IP
expected: Run `python -m pytest tests/test_pipeline/test_dns_resolver.py -v`. All 12 tests pass. The resolve_hostname function returns a hostname string for IPs with PTR records (mocked in tests).
result: pass

### 3. DNS Timeout — No PTR Record
expected: Run `python -m pytest tests/test_pipeline/test_dns_resolver.py::test_timeout_fires -v`. Test passes — confirms asyncio.wait_for fires at 2 seconds and returns the raw IP, not a hostname.
result: pass

### 4. DNS Cache — No Duplicate Lookups
expected: Run `python -m pytest tests/test_pipeline/test_dns_resolver.py::test_cache_hit -v`. Test passes — confirms socket.gethostbyaddr is called only once for the same IP within TTL window (cache hit on second call).
result: pass

### 5. GeoIP Enrichment — Country + ASN
expected: Run `python -m pytest tests/test_pipeline/test_geo_enricher.py -v`. All 8 tests pass. enrich_geo returns dst_country (2-letter ISO code), dst_asn ("AS{number}"), dst_org for known IPs.
result: pass

### 6. GeoIP Graceful Degradation — Missing DB
expected: Run `python -m pytest tests/test_pipeline/test_geo_enricher.py::test_missing_db_warning -v`. Test passes — confirms that when MMDB files are absent, pipeline continues with null geo fields and logs a GEOIP_STALE warning.
result: pass

### 7. Threat Intel — Blocklisted IP Flagged
expected: Run `python -m pytest tests/test_pipeline/test_threat_intel.py::test_blocklisted_ip tests/test_pipeline/test_threat_intel.py::test_flag_fields -v`. Both tests pass — a blocklisted IP produces threat_intel.is_blocklisted=True and source="ipsum".
result: pass

### 8. Pipeline Enrichment Wiring — All Stages In Sequence
expected: Run `python -m pytest tests/test_pipeline/test_worker.py::test_enrichment_stages_wired -v`. Test passes — confirms enrich_dns, enrich_geo, check_threat_intel are all called in sequence for each event.
result: pass

### 9. Full Test Suite Green
expected: Run `python -m pytest tests/ -q`. All 70 tests pass with 0 failures.
result: pass

## Summary

total: 9
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 1

## Gaps

[none yet]
