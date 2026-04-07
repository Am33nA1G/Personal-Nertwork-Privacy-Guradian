@echo off
REM Apply database schema for PNPG
REM This batch file runs the Python schema migration script

echo ============================================================
echo PNPG Database Schema Migration
echo ============================================================
echo.

cd /d "%~dp0.."
python tools\apply_schema.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo SUCCESS! Schema applied successfully.
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo ERROR! Schema migration failed.
    echo ============================================================
    exit /b 1
)

pause
