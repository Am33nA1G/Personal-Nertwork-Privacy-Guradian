@echo off
REM Apply schema using psql directly
REM Alternative method if Python approach doesn't work

echo ============================================================
echo PNPG Database Schema Migration (psql method)
echo ============================================================
echo.

cd /d "%~dp0"

set PGPASSWORD=pnpg
psql -h localhost -p 5433 -U pnpg -d pnpg -f pnpg\db\schema.sql

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo SUCCESS! Schema applied successfully.
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo ERROR! psql command failed.
    echo Make sure PostgreSQL client tools are installed.
    echo Alternatively, run: python tools\apply_schema.py
    echo ============================================================
    exit /b 1
)

pause
