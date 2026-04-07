"""SQL query constants for the Phase 5 data layer."""

INSERT_CONNECTION = """
INSERT INTO connections (
    event_id, timestamp, process_name, process_path, pid,
    src_ip, src_port, dst_ip, dst_port, dst_hostname,
    dst_country, dst_asn, dst_org, protocol,
    bytes_sent, bytes_recv, state, is_blocklisted,
    blocklist_source, severity, raw
) VALUES (
    $1, $2, $3, $4, $5,
    $6, $7, $8, $9, $10,
    $11, $12, $13, $14,
    $15, $16, $17, $18,
    $19, $20, $21
)
ON CONFLICT (event_id) DO NOTHING
"""

INSERT_ALERT = """
INSERT INTO alerts (
    alert_id, timestamp, severity, rule_id, reason,
    confidence, process_name, pid, dst_ip, dst_hostname,
    recommended_action, suppressed, status
) VALUES (
    $1, $2, $3, $4, $5,
    $6, $7, $8, $9, $10,
    $11, $12, $13
)
ON CONFLICT (alert_id) DO NOTHING
"""

UPSERT_PROCESS = """
INSERT INTO processes (process_name, process_path, first_seen, last_seen)
VALUES ($1, $2, $3, $3)
ON CONFLICT (process_name) DO UPDATE
SET process_path = EXCLUDED.process_path,
    last_seen = EXCLUDED.last_seen
"""

SELECT_CONNECTIONS = """
SELECT *
FROM connections
WHERE ($1::text IS NULL OR process_name = $1)
  AND ($2::text IS NULL OR dst_ip = $2)
  AND ($3::timestamptz IS NULL OR timestamp >= $3)
  AND ($4::timestamptz IS NULL OR timestamp <= $4)
ORDER BY timestamp DESC
LIMIT $5 OFFSET $6
"""

COUNT_CONNECTIONS = """
SELECT COUNT(*)
FROM connections
WHERE ($1::text IS NULL OR process_name = $1)
  AND ($2::text IS NULL OR dst_ip = $2)
  AND ($3::timestamptz IS NULL OR timestamp >= $3)
  AND ($4::timestamptz IS NULL OR timestamp <= $4)
"""

SELECT_ALERTS = """
SELECT *
FROM alerts
WHERE ($1::text IS NULL OR status = $1)
  AND ($2::text IS NULL OR severity = $2)
  AND ($3::timestamptz IS NULL OR timestamp >= $3)
  AND ($4::timestamptz IS NULL OR timestamp <= $4)
ORDER BY timestamp DESC
LIMIT $5 OFFSET $6
"""

COUNT_ALERTS = """
SELECT COUNT(*)
FROM alerts
WHERE ($1::text IS NULL OR status = $1)
  AND ($2::text IS NULL OR severity = $2)
  AND ($3::timestamptz IS NULL OR timestamp >= $3)
  AND ($4::timestamptz IS NULL OR timestamp <= $4)
"""

STATS_SUMMARY = """
SELECT
    (SELECT COUNT(*) FROM connections
     WHERE timestamp >= NOW() - INTERVAL '24 hours') AS total_connections,
    (SELECT COUNT(DISTINCT dst_ip) FROM connections
     WHERE timestamp >= NOW() - INTERVAL '24 hours') AS unique_destinations,
    (SELECT COUNT(*) FROM alerts
     WHERE status = 'active'
       AND timestamp >= NOW() - INTERVAL '24 hours') AS active_alerts,
    (
        SELECT COALESCE(
            json_agg(
                json_build_object(
                    'process_name', process_name,
                    'count', process_count
                )
                ORDER BY process_count DESC
            ),
            '[]'::json
        )
        FROM (
            SELECT process_name, COUNT(*) AS process_count
            FROM connections
            WHERE timestamp >= NOW() - INTERVAL '24 hours'
            GROUP BY process_name
            ORDER BY process_count DESC
            LIMIT 10
        ) AS top_processes
    ) AS top_processes
"""

STATS_TIMESERIES = """
SELECT date_trunc($1, timestamp) AS bucket, COUNT(*) AS count
FROM connections
WHERE timestamp >= $2
  AND timestamp <= $3
GROUP BY bucket
ORDER BY bucket
"""

PURGE_CONNECTIONS = """
WITH deleted AS (
    SELECT event_id
    FROM connections
    WHERE timestamp < NOW() - make_interval(days => $1)
    LIMIT 10000
)
DELETE FROM connections
WHERE event_id IN (SELECT event_id FROM deleted)
"""

PURGE_ALERTS = """
WITH deleted AS (
    SELECT alert_id
    FROM alerts
    WHERE timestamp < NOW() - make_interval(days => $1)
    LIMIT 10000
)
DELETE FROM alerts
WHERE alert_id IN (SELECT alert_id FROM deleted)
"""

SELECT_ALLOWLIST = """
SELECT *
FROM allowlist
ORDER BY created_at DESC
"""

INSERT_ALLOWLIST = """
INSERT INTO allowlist (process_name, dst_ip, dst_hostname, expires_at, reason)
VALUES ($1, $2, $3, $4, $5)
RETURNING *
"""

DELETE_ALLOWLIST = """
DELETE FROM allowlist
WHERE rule_id = $1
RETURNING *
"""

SELECT_SUPPRESSIONS = """
SELECT *
FROM suppressions
ORDER BY created_at DESC
"""

INSERT_SUPPRESSION = """
INSERT INTO suppressions (rule_id, process_name, scope, reason, alert_id)
VALUES ($1, $2, $3, $4, $5)
RETURNING *
"""

UPDATE_ALERT_STATUS = """
UPDATE alerts
SET status = $2,
    suppressed = ($2 = 'suppressed')
WHERE alert_id = $1
RETURNING *
"""

INSERT_THREAT = """
INSERT INTO threats (
    severity, threat_type, process_name, pid, dst_ip,
    dst_hostname, reason, confidence, status, alert_id
) VALUES (
    $1, $2, $3, $4, $5,
    $6, $7, $8, $9, $10
)
RETURNING *
"""

SELECT_THREATS = """
SELECT *
FROM threats
WHERE ($1::text IS NULL OR status = $1)
  AND ($2::text IS NULL OR severity = $2)
  AND ($3::timestamptz IS NULL OR detected_at >= $3)
  AND ($4::timestamptz IS NULL OR detected_at <= $4)
ORDER BY detected_at DESC
LIMIT $5 OFFSET $6
"""

COUNT_THREATS = """
SELECT COUNT(*)
FROM threats
WHERE ($1::text IS NULL OR status = $1)
  AND ($2::text IS NULL OR severity = $2)
  AND ($3::timestamptz IS NULL OR detected_at >= $3)
  AND ($4::timestamptz IS NULL OR detected_at <= $4)
"""

UPDATE_THREAT_STATUS = """
UPDATE threats
SET status = $2,
    remediation_status = $3,
    killed_at = CASE WHEN $3 = 'killed' THEN NOW() ELSE killed_at END,
    block_ip_at = CASE WHEN $3 = 'blocked' THEN NOW() ELSE block_ip_at END
WHERE threat_id = $1
RETURNING *
"""

GET_THREAT_BY_PID = """
SELECT *
FROM threats
WHERE pid = $1 AND status = 'active'
ORDER BY detected_at DESC
LIMIT 1
"""
