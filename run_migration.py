#!/usr/bin/env python3
"""Execute the migration script and report results."""
import subprocess
import sys

print("Attempting to run schema migration...")
print("-" * 60)

result = subprocess.run(
    [sys.executable, "tools/migrate_now.py"],
    capture_output=True,
    text=True,
    cwd=r"C:\Users\alame\Desktop\network Lab project"
)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

sys.exit(result.returncode)
