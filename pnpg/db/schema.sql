CREATE TABLE IF NOT EXISTS connections (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    process_name TEXT NOT NULL,
    process_path TEXT,
    pid INTEGER,
    src_ip TEXT,
    src_port INTEGER,
    dst_ip TEXT,
    dst_port INTEGER,
    dst_hostname TEXT,
    dst_country TEXT,
    dst_asn TEXT,
    dst_org TEXT,
    protocol TEXT,
    bytes_sent BIGINT DEFAULT 0,
    bytes_recv BIGINT DEFAULT 0,
    state TEXT,
    is_blocklisted BOOLEAN DEFAULT FALSE,
    blocklist_source TEXT,
    severity TEXT NOT NULL DEFAULT 'INFO',
    raw JSONB
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    severity TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    reason TEXT,
    confidence REAL,
    process_name TEXT,
    pid INTEGER,
    dst_ip TEXT,
    dst_hostname TEXT,
    recommended_action TEXT,
    suppressed BOOLEAN DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS processes (
    process_name TEXT PRIMARY KEY,
    process_path TEXT,
    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS allowlist (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_name TEXT,
    dst_ip TEXT,
    dst_hostname TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason TEXT
);

CREATE TABLE IF NOT EXISTS suppressions (
    suppression_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rule_id TEXT,
    process_name TEXT,
    scope TEXT NOT NULL,
    reason TEXT,
    alert_id UUID REFERENCES alerts(alert_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS threats (
    threat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    severity TEXT NOT NULL,
    threat_type TEXT NOT NULL,
    process_name TEXT NOT NULL,
    pid INTEGER NOT NULL,
    dst_ip TEXT NOT NULL,
    dst_hostname TEXT,
    reason TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    remediation_status TEXT DEFAULT NULL,
    killed_at TIMESTAMPTZ,
    block_ip_at TIMESTAMPTZ,
    alert_id UUID REFERENCES alerts(alert_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_connections_ts_proc
    ON connections (timestamp DESC, process_name);
CREATE INDEX IF NOT EXISTS idx_connections_dst_ip ON connections (dst_ip);
CREATE INDEX IF NOT EXISTS idx_alerts_ts_severity
    ON alerts (timestamp DESC, severity);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status);
CREATE INDEX IF NOT EXISTS idx_threats_detected_at
    ON threats (detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_threats_status ON threats (status);
CREATE INDEX IF NOT EXISTS idx_threats_pid ON threats (pid);
