"""Direct schema application - runs independently"""
import asyncio
import sys
from pathlib import Path

# Embedded schema SQL - no file dependencies
SCHEMA_SQL = """
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
"""

async def main():
    try:
        import asyncpg
    except ImportError:
        print("ERROR: asyncpg not installed")
        print("Run: pip install asyncpg")
        return False
    
    # Try config file, fall back to default
    dsn = "postgresql://pnpg:pnpg@localhost:5433/pnpg"
    config_path = Path(__file__).parent.parent / "config.yaml"
    
    if config_path.exists():
        try:
            import yaml
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                dsn = config.get("db_dsn", dsn)
        except:
            pass  # Use default
    
    print("=" * 60)
    print("PNPG Schema Migration")
    print("=" * 60)
    print(f"\nConnecting to: {dsn.split('@')[1] if '@' in dsn else dsn}")
    
    try:
        conn = await asyncpg.connect(dsn)
        print("✓ Connected")
    except Exception as e:
        print(f"\n✗ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check PostgreSQL is running: docker ps | findstr postgres")
        print("2. Verify credentials in config.yaml")
        print("3. Create database: createdb -U pnpg pnpg")
        return False
    
    try:
        print("\nApplying schema...")
        await conn.execute(SCHEMA_SQL)
        print("✓ Schema applied")
        
        # Verify
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        
        print(f"\n✓ Created {len(tables)} tables:")
        for row in tables:
            print(f"  • {row['tablename']}")
        
        print("\n" + "=" * 60)
        print("SUCCESS - Database ready!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. python -m pnpg.main")
        print("2. cd frontend && npm run dev")
        print("3. Open http://localhost:3000")
        return True
        
    except Exception as e:
        print(f"\n✗ Schema application failed: {e}")
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
