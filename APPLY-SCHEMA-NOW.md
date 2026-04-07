# ⚠️ IMPORTANT: Database Schema Must Be Applied

## Current Status
- ❌ Database schema NOT yet applied
- ✅ Schema files ready
- ✅ Migration tools created
- ✅ Safe connection features implemented

## What You Need to Do

### Step 1: Apply the Schema

Open a command prompt or terminal and run **ONE** of these:

#### Option A: Standalone Migration Script (Easiest)
```cmd
cd "C:\Users\alame\Desktop\network Lab project"
python tools\migrate_now.py
```

#### Option B: Original Script
```cmd
cd "C:\Users\alame\Desktop\network Lab project"
python tools\apply_schema.py
```

#### Option C: Batch File
```cmd
cd "C:\Users\alame\Desktop\network Lab project"
apply-schema.bat
```

#### Option D: psql Command
```cmd
cd "C:\Users\alame\Desktop\network Lab project"
set PGPASSWORD=pnpg
psql -h localhost -p 5433 -U pnpg -d pnpg -f pnpg\db\schema.sql
```

### Step 2: Verify Success

You should see output like:
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

### Step 3: Start the Application

**Terminal 1:**
```cmd
cd "C:\Users\alame\Desktop\network Lab project"
python -m pnpg.main
```

**Terminal 2:**
```cmd
cd "C:\Users\alame\Desktop\network Lab project\frontend"
npm run dev
```

**Browser:**
```
http://localhost:3000
```

## Troubleshooting

### "Connection failed" Error

**Cause:** PostgreSQL not running or wrong credentials

**Fix:**
1. Check if PostgreSQL is running:
   ```cmd
   netstat -an | findstr 5433
   ```

2. Start PostgreSQL (if using Docker):
   ```cmd
   docker start <postgres_container>
   ```

3. Check if database exists:
   ```cmd
   set PGPASSWORD=pnpg
   psql -h localhost -p 5433 -U pnpg -l
   ```

4. Create database if missing:
   ```cmd
   set PGPASSWORD=pnpg
   createdb -h localhost -p 5433 -U pnpg pnpg
   ```

### "asyncpg not installed" Error

**Cause:** Python dependencies not installed

**Fix:**
```cmd
pip install -r requirements.txt
```

### "psql is not recognized" Error

**Cause:** PostgreSQL client not in PATH

**Fix:** Use Option A or B (Python scripts) instead of psql

## What Happens After Schema is Applied

Once the schema is successfully applied:

1. ✅ **Threats endpoint works** - GET /api/v1/threats returns data
2. ✅ **Alerts can be suppressed** - PATCH /api/v1/alerts/{id} works
3. ✅ **Allowlist can be managed** - POST/GET/DELETE /api/v1/allowlist works
4. ✅ **All safe connection features are active**

## Files Created For You

| File | Purpose |
|------|---------|
| `tools/migrate_now.py` | Standalone migration (embedded SQL, no file deps) |
| `tools/apply_schema.py` | Original migration (reads schema.sql) |
| `apply-schema.bat` | Windows batch file (runs Python script) |
| `apply-schema-psql.bat` | Windows batch file (runs psql) |
| `run_migration.py` | Wrapper script |

**All are ready to use. Pick whichever works for your environment.**

## Why This Wasn't Done Automatically

The migration requires:
- PostgreSQL running and accessible
- Admin/elevated permissions (depending on setup)
- User confirmation (don't auto-create tables without permission)

**That's why you need to run one command manually to apply the schema.**

---

## Summary

**Current state:** Everything is ready, schema just needs to be applied

**Your action:** Run **one** of the migration commands above

**Expected time:** < 1 minute

**After that:** All features work immediately, no code changes needed
