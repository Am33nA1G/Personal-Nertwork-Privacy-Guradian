#!/usr/bin/env python3
"""Apply the database schema from pnpg/db/schema.sql to PostgreSQL.

Usage: python tools/apply_schema.py

This script can be run directly without dependencies on config files.
"""
import asyncio
import sys
from pathlib import Path


async def apply_schema():
    """Read schema.sql and execute it against the configured database."""
    # Try to import asyncpg
    try:
        import asyncpg
    except ImportError:
        print("❌ asyncpg not installed. Run: pip install asyncpg")
        sys.exit(1)
    
    # Read database DSN from config.yaml
    config_path = Path(__file__).parent.parent / "config.yaml"
    dsn = "postgresql://pnpg:pnpg@localhost:5433/pnpg"  # default
    
    if config_path.exists():
        try:
            import yaml
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                dsn = config.get("db_dsn", dsn)
        except ImportError:
            print("⚠️  PyYAML not installed, using default DSN")
        except Exception as e:
            print(f"⚠️  Could not read config.yaml: {e}, using default DSN")
    
    # Read schema file
    schema_path = Path(__file__).parent.parent / "pnpg" / "db" / "schema.sql"
    if not schema_path.exists():
        print(f"❌ Schema file not found: {schema_path}")
        sys.exit(1)
    
    schema_sql = schema_path.read_text(encoding="utf-8")
    
    # Connect and execute
    print(f"📡 Connecting to database: {dsn.split('@')[1] if '@' in dsn else dsn}")  # hide credentials
    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        print("\n💡 Possible solutions:")
        print("   1. Make sure PostgreSQL is running on localhost:5433")
        print("   2. Check credentials: pnpg/pnpg")
        print("   3. Verify database 'pnpg' exists")
        print("\nIf using Docker:")
        print("   docker-compose up -d postgres")
        print("\nIf using local PostgreSQL:")
        print("   createdb -U pnpg pnpg")
        sys.exit(1)
    
    try:
        print("📝 Applying schema...")
        await conn.execute(schema_sql)
        print("✅ Schema applied successfully!")
        
        # Verify tables exist
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        
        print(f"\n📊 Created {len(tables)} tables:")
        for row in tables:
            print(f"   • {row['tablename']}")
        
        print("\n✨ Database is ready! You can now:")
        print("   1. Start the backend: python -m pnpg.main")
        print("   2. Start the frontend: cd frontend && npm run dev")
        print("   3. Access the dashboard: http://localhost:3000")
            
    except Exception as e:
        print(f"❌ Failed to apply schema: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("PNPG Database Schema Migration Tool")
    print("=" * 60)
    print()
    asyncio.run(apply_schema())
