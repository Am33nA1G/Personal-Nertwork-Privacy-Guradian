---
status: complete
phase: 04-detection-engine
source: [roadmap success criteria, plan acceptance criteria]
started: 2026-04-05T00:00:00Z
updated: 2026-04-05
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start - imports and DetectorState init
expected: Run: `python -c "from pnpg.pipeline.detector import DetectorState, detect_event, load_tor_exit_nodes; s = DetectorState(); print('ok', s)"` - output shows "ok DetectorState(...)" with no errors.
result: pass

### 2. DET-01 - unknown domain fires WARNING alert
expected: Run: `python -m pytest tests/test_pipeline/test_detector.py -k "det01" -v` - all DET-01 tests pass. Specifically: public IP with no DNS resolution fires WARNING alert; private IP (192.168.x.x) does NOT fire; resolved hostname does NOT fire.
result: pass

### 3. DET-02 - rate spike fires HIGH alert
expected: Run: `python -m pytest tests/test_pipeline/test_detector.py -k "det02" -v` - all DET-02 tests pass. >100 connections/min from same process fires HIGH alert; exactly 100 does not.
result: pass

### 4. DET-03 - unusual port with false-positive gate
expected: Run: `python -m pytest tests/test_pipeline/test_detector.py -k "det03" -v` - all DET-03 tests pass. Unusual port from "unknown process" fires alert. Same port from known process (e.g. chrome.exe) at normal rate does NOT fire (false-positive gate confirmed).
result: pass

### 5. DET-04 - unknown process fires ALERT
expected: Run: `python -m pytest tests/test_pipeline/test_detector.py -k "det04" -v` - process_name "unknown process" fires DET-04 ALERT; "chrome.exe" does not.
result: pass

### 6. DET-05 - blocklisted IP fires CRITICAL alert
expected: Run: `python -m pytest tests/test_pipeline/test_detector.py -k "det05" -v` - threat_intel.is_blocklisted=True fires DET-05 CRITICAL; False does not.
result: pass

### 7. DET-06 - TOR exit node fires HIGH alert
expected: Run: `python -m pytest tests/test_pipeline/test_detector.py -k "det06" -v` - dst_ip matching a TOR exit node fires DET-06 HIGH; non-matching IP does not.
result: pass

### 8. DET-07 - new destination fires LOW discovery alert
expected: Run: `python -m pytest tests/test_pipeline/test_detector.py -k "det07" -v` - first connection from process to dst_ip fires DET-07 LOW; second identical connection does NOT fire.
result: pass

### 9. DET-09 - alert rate limiter (1 per rule per process per second)
expected: Run: `python -m pytest tests/test_pipeline/test_detector.py -k "rate_limit" -v` - rapid repeated alerts for same rule+process are suppressed; only 1 per second passes through.
result: pass

### 10. ALLOW - allowlist suppresses matching alerts
expected: Run: `python -m pytest tests/test_pipeline/test_detector.py -k "allowlist" -v` - connection matching an allowlist rule produces no alert; expired allowlist rule does NOT suppress.
result: pass

### 11. SUPP - suppression store blocks by rule+process
expected: Run: `python -m pytest tests/test_pipeline/test_detector.py -k "suppress" -v` - alert suppressed when rule_id+process_name is in suppressed_rules set.
result: pass

### 12. DET-08 - no magic numbers in detection code
expected: Run: `grep -n "100\|0\.85\|0\.95\|0\.9\|0\.7\|0\.6\|0\.5\|0\.3" pnpg/pipeline/detector.py` - any numeric literals that appear are only in confidence/threshold values inside rule functions that read from config. The rate threshold 100 must NOT appear hardcoded; only `config.get("connection_rate_threshold_per_min", 100)` form is acceptable.
result: pass

### 13. Full suite still green - no regressions
expected: Run: `python -m pytest tests/ -x -q` - all 108 tests pass, 0 failures, 0 errors.
result: pass

## Summary

total: 13
passed: 13
issues: 0
blocked: 0
skipped: 0
pending: 0

## Gaps

[none yet]
