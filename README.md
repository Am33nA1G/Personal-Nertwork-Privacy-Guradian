# Personal Network Privacy Guardian (PNPG)

Real-time network monitoring system with process attribution, GeoIP enrichment, and anomaly detection.

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (running on localhost:5433)

### 2. Database Setup

**IMPORTANT:** You must apply the database schema before starting the application.

**Quick method (recommended):**
```bash
python tools/migrate_now.py
```

**Alternative methods:**
```bash
# Method 2: Original script
python tools/apply_schema.py

# Method 3: Batch file (Windows)
apply-schema.bat

# Method 4: Wrapper script
python run_migration.py

# Method 5: psql directly
set PGPASSWORD=pnpg
psql -h localhost -p 5433 -U pnpg -d pnpg -f pnpg/db/schema.sql
```

**Expected output:**
```
============================================================
PNPG Schema Migration
============================================================

Connecting to: localhost:5433/pnpg
✓ Connected

Applying schema...
✓ Schema applied

✓ Created 6 tables:
  • alerts
  • allowlist
  • connections
  • processes
  • suppressions
  • threats

============================================================
SUCCESS - Database ready!
============================================================
```

**If you get "Connection failed":**
1. Make sure PostgreSQL is running on port 5433
2. Check credentials: username=pnpg, password=pnpg, database=pnpg
3. Create database if missing: `createdb -h localhost -p 5433 -U pnpg pnpg`

### 3. Install Dependencies

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### 4. Start the Application

**Terminal 1 - Backend:**
```bash
python -m pnpg.main
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

**Access the dashboard:**
- Open browser: http://localhost:3000
- Default login: `admin` / `admin`

## Features

### ✅ Network Monitoring
- Real-time packet capture with Scapy
- Process-to-connection mapping via psutil
- DNS resolution and GeoIP enrichment
- Live WebSocket streaming to dashboard

### ✅ Alert Management
- **Suppress** false positive alerts
- **Resolve** legitimate alerts
- View suppression history
- In-memory detection state sync

### ✅ Allowlist System
- Add safe processes, IPs, and hostnames
- Optional expiration timestamps
- Prevent future alerts for trusted connections
- Full CRUD interface

### ✅ Threat Remediation
- Kill malicious processes
- Block IPs via Windows Firewall
- Confirmation dialogs for safety
- Track remediation status

## Project Structure

```
pnpg/
├── api/              # FastAPI routes and middleware
│   ├── routes/       # Endpoints (alerts, threats, allowlist, etc.)
│   ├── auth.py       # JWT authentication
│   └── middleware.py # Rate limiting
├── capture/          # Packet capture layer (Scapy)
├── pipeline/         # Event processing pipeline
│   ├── detector.py   # Anomaly detection engine
│   ├── dns_resolver.py
│   ├── geo_enricher.py
│   └── process_mapper.py
├── db/               # Database layer
│   ├── schema.sql    # PostgreSQL schema
│   ├── pool.py       # asyncpg connection pool
│   └── queries.py    # SQL queries
├── storage/          # Data persistence
└── ws/               # WebSocket manager

frontend/
├── components/       # React components
│   ├── AlertsPanel.tsx
│   ├── ThreatsPanel.tsx
│   ├── AllowlistManager.tsx
│   └── ...
├── pages/            # Next.js pages
├── lib/              # API client and types
└── hooks/            # Custom React hooks

tools/
└── apply_schema.py   # Database migration tool
```

## Configuration

Edit `config.yaml`:

```yaml
# Database connection
db_dsn: postgresql://pnpg:pnpg@localhost:5433/pnpg

# Detection thresholds
connection_rate_threshold: 50
connection_rate_threshold_per_min: 100

# Network interface (null = auto-select)
interface: null

# Logging
log_dir: logs
log_rotation_size_mb: 50
debug_mode: false
```

## Common Issues

### "Failed to load threats" Error

**Problem:** Database schema not applied

**Solution:** Run `python tools/apply_schema.py`

### "Database unavailable" Error

**Problem:** PostgreSQL not running or wrong connection string

**Solutions:**
1. Start PostgreSQL: `docker-compose up -d postgres` (if using Docker)
2. Check connection in config.yaml
3. Verify database exists: `psql -h localhost -p 5433 -U pnpg -l`

### "Npcap not found" Error (Windows)

**Problem:** Npcap driver not installed

**Solution:** Download and install from https://npcap.com

### "Permission denied" Error

**Problem:** Application requires admin/root privileges

**Solution:** Run as administrator (Windows) or with sudo (Linux)

## Development

### Run Tests
```bash
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

### Type Checking
```bash
cd frontend
npm run type-check
```

## Tech Stack

**Backend:**
- FastAPI (async web framework)
- Scapy (packet capture)
- psutil (process mapping)
- asyncpg (PostgreSQL driver)
- uvicorn (ASGI server)

**Frontend:**
- Next.js 14
- React 18
- TypeScript
- Recharts (data visualization)
- Bootstrap 5

**Database:**
- PostgreSQL 15+

## License

Confidential - Internal Use Only

## Support

For issues or questions, see the documentation in `.copilot/session-state/` or check the PRD.md.
