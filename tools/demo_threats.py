#!/usr/bin/env python3
"""Generate demo threats and alerts for PNPG demonstrations.

Usage:
    # Generate sample threats
    python tools/demo_threats.py

    # Generate threats + alerts
    python tools/demo_threats.py --with-alerts

    # Clear all demo data
    python tools/demo_threats.py --clear
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg not installed")
    print("Run: pip install asyncpg")
    sys.exit(1)


DEMO_THREATS = [
    {
        "severity": "CRITICAL",
        "threat_type": "Malware Connection",
        "process_name": "suspicious.exe",
        "pid": 8432,
        "dst_ip": "185.220.101.45",
        "dst_hostname": "malicious-c2.example.com",
        "reason": "Process attempting connection to known malware C2 server (blocklisted IP)",
        "confidence": 0.95,
    },
    {
        "severity": "HIGH",
        "threat_type": "Data Exfiltration",
        "process_name": "backdoor.exe",
        "pid": 7721,
        "dst_ip": "103.224.182.245",
        "dst_hostname": None,
        "reason": "Unusual outbound data transfer rate (2.4 GB in 5 minutes) to unknown destination",
        "confidence": 0.87,
    },
    {
        "severity": "CRITICAL",
        "threat_type": "Cryptominer",
        "process_name": "svchost32.exe",
        "pid": 9156,
        "dst_ip": "45.142.213.99",
        "dst_hostname": "mining-pool.suspicious.net",
        "reason": "Process name mimicking system service, connecting to cryptocurrency mining pool",
        "confidence": 0.92,
    },
    {
        "severity": "HIGH",
        "threat_type": "Phishing Callback",
        "process_name": "chrome.exe",
        "pid": 4832,
        "dst_ip": "193.56.146.78",
        "dst_hostname": "tracking-phish-kit.example",
        "reason": "Browser connecting to known phishing infrastructure after suspicious download",
        "confidence": 0.79,
    },
]

DEMO_ALERTS = [
    {
        "severity": "WARNING",
        "rule_id": "connection_rate_exceeded",
        "reason": "Process zoom.exe made 127 connections in 60 seconds (threshold: 100)",
        "confidence": 0.65,
        "process_name": "zoom.exe",
        "pid": 5234,
        "dst_ip": "13.107.42.14",
        "dst_hostname": "zoom.us",
        "recommended_action": "Verify this is legitimate Zoom activity or add to allowlist",
    },
    {
        "severity": "ALERT",
        "rule_id": "unknown_process",
        "reason": "Process updater.exe is not in known-good list and made external connection",
        "confidence": 0.72,
        "process_name": "updater.exe",
        "pid": 6721,
        "dst_ip": "104.16.123.96",
        "dst_hostname": "cdn-update.example.com",
        "recommended_action": "Investigate process origin and legitimacy",
    },
    {
        "severity": "WARNING",
        "rule_id": "uncommon_port",
        "reason": "Chrome connected to port 8888 (non-standard web port)",
        "confidence": 0.58,
        "process_name": "chrome.exe",
        "pid": 4832,
        "dst_ip": "172.217.14.238",
        "dst_hostname": "example-dev-server.com",
        "recommended_action": "Verify if this is a development/testing server",
    },
]


async def get_connection(dsn: str):
    """Connect to PostgreSQL."""
    try:
        return await asyncpg.connect(dsn)
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
        print("\nMake sure:")
        print("1. PostgreSQL is running")
        print("2. Schema is applied: python tools/migrate_now.py")
        print("3. Connection string is correct in config.yaml")
        sys.exit(1)


async def insert_threats(conn, count: int = None):
    """Insert demo threats into the database."""
    threats = DEMO_THREATS if count is None else DEMO_THREATS[:count]
    
    print(f"\n📝 Inserting {len(threats)} demo threats...")
    
    for i, threat in enumerate(threats, 1):
        threat_id = await conn.fetchval(
            """
            INSERT INTO threats (
                severity, threat_type, process_name, pid, dst_ip, dst_hostname,
                reason, confidence, status, detected_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'active', $9)
            RETURNING threat_id
            """,
            threat["severity"],
            threat["threat_type"],
            threat["process_name"],
            threat["pid"],
            threat["dst_ip"],
            threat["dst_hostname"],
            threat["reason"],
            threat["confidence"],
            datetime.now() - timedelta(minutes=5-i),  # Stagger timestamps
        )
        print(f"  ✓ Threat {i}: {threat['process_name']} (PID {threat['pid']}) - {threat['threat_type']}")
    
    print(f"\n✅ Inserted {len(threats)} threats successfully!")


async def insert_alerts(conn, count: int = None):
    """Insert demo alerts into the database."""
    alerts = DEMO_ALERTS if count is None else DEMO_ALERTS[:count]
    
    print(f"\n📝 Inserting {len(alerts)} demo alerts...")
    
    for i, alert in enumerate(alerts, 1):
        alert_id = await conn.fetchval(
            """
            INSERT INTO alerts (
                alert_id, severity, rule_id, reason, confidence, process_name,
                pid, dst_ip, dst_hostname, recommended_action, status, timestamp
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'active', $11)
            RETURNING alert_id
            """,
            uuid4(),
            alert["severity"],
            alert["rule_id"],
            alert["reason"],
            alert["confidence"],
            alert["process_name"],
            alert["pid"],
            alert["dst_ip"],
            alert["dst_hostname"],
            alert["recommended_action"],
            datetime.now() - timedelta(minutes=10-i),  # Stagger timestamps
        )
        print(f"  ✓ Alert {i}: {alert['rule_id']} - {alert['process_name']}")
    
    print(f"\n✅ Inserted {len(alerts)} alerts successfully!")


async def clear_demo_data(conn):
    """Clear all threats and alerts from the database."""
    print("\n🗑️  Clearing demo data...")
    
    threats_deleted = await conn.fetchval("DELETE FROM threats RETURNING COUNT(*)")
    alerts_deleted = await conn.fetchval("DELETE FROM alerts RETURNING COUNT(*)")
    
    print(f"  ✓ Deleted {threats_deleted} threats")
    print(f"  ✓ Deleted {alerts_deleted} alerts")
    print("\n✅ Demo data cleared!")


async def show_current_data(conn):
    """Display current threats and alerts."""
    threats = await conn.fetch("SELECT * FROM threats WHERE status = 'active' ORDER BY detected_at DESC")
    alerts = await conn.fetch("SELECT * FROM alerts WHERE status = 'active' ORDER BY timestamp DESC")
    
    print(f"\n📊 Current Data:")
    print(f"  • {len(threats)} active threats")
    print(f"  • {len(alerts)} active alerts")
    
    if threats:
        print("\n🚨 Active Threats:")
        for t in threats:
            print(f"  • {t['process_name']} (PID {t['pid']}) - {t['threat_type']} [{t['severity']}]")
    
    if alerts:
        print("\n⚠️  Active Alerts:")
        for a in alerts:
            print(f"  • {a['process_name']} - {a['rule_id']} [{a['severity']}]")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate demo threats for PNPG demonstrations")
    parser.add_argument("--with-alerts", action="store_true", help="Also generate demo alerts")
    parser.add_argument("--clear", action="store_true", help="Clear all demo data")
    parser.add_argument("--threats-only", type=int, metavar="N", help="Insert only N threats")
    parser.add_argument("--alerts-only", type=int, metavar="N", help="Insert only N alerts")
    parser.add_argument("--show", action="store_true", help="Show current data")
    args = parser.parse_args()
    
    # Load DSN from config
    config_path = Path(__file__).parent.parent / "config.yaml"
    dsn = "postgresql://pnpg:pnpg@localhost:5433/pnpg"
    
    if config_path.exists():
        try:
            import yaml
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                dsn = config.get("db_dsn", dsn)
        except:
            pass
    
    print("=" * 60)
    print("PNPG Demo Data Generator")
    print("=" * 60)
    print(f"Database: {dsn.split('@')[1] if '@' in dsn else dsn}")
    
    conn = await get_connection(dsn)
    
    try:
        if args.clear:
            await clear_demo_data(conn)
        elif args.show:
            await show_current_data(conn)
        elif args.threats_only is not None:
            await insert_threats(conn, args.threats_only)
        elif args.alerts_only is not None:
            await insert_alerts(conn, args.alerts_only)
        else:
            # Default: insert threats, optionally alerts
            await insert_threats(conn)
            if args.with_alerts:
                await insert_alerts(conn)
        
        # Always show current data at the end
        if not args.show:
            await show_current_data(conn)
        
        print("\n" + "=" * 60)
        print("✨ Demo data ready!")
        print("=" * 60)
        print("\n📋 Next steps:")
        print("1. Refresh your dashboard at http://localhost:3000")
        print("2. Click the 'Threats' tab to see demo threats")
        print("3. Click '⚔️ Kill' or '🚫 Block IP' to demonstrate remediation")
        print("\nTo clear demo data later:")
        print("  python tools/demo_threats.py --clear")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
