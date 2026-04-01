"""Startup prerequisite checks for PNPG.

CAP-02: Verify Npcap is installed before any packet capture attempt.
CAP-03: Verify the process is running with administrator privileges.

Both functions print a clear error to stderr and exit with code 1 on failure.
They return None on success. This is a cold-start gate — call both before
starting Scapy or any network activity.
"""
import ctypes
import logging
import os
import sys
import winreg

logger = logging.getLogger(__name__)


def check_npcap() -> None:
    """Verify Npcap is installed on the system.

    Uses two detection strategies (matching Scapy's own detection approach):
    1. Check for the Npcap DLL directory in System32.
    2. Check the Windows registry for Npcap service/software keys.

    Exits with code 1 and prints a clear error if Npcap is not found.
    Returns None if Npcap is detected.

    Requirement: CAP-02
    """
    windir = os.environ.get("WINDIR", "C:\\Windows")
    npcap_system32 = os.path.join(windir, "System32", "Npcap")

    # Strategy 1: filesystem check
    if os.path.isdir(npcap_system32):
        return None

    # Strategy 2: registry check
    registry_keys = [
        r"SOFTWARE\Npcap",
        r"SYSTEM\CurrentControlSet\Services\npcap",
    ]
    for key_path in registry_keys:
        try:
            winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            return None
        except FileNotFoundError:
            continue
        except OSError:
            continue

    # Neither check passed — Npcap is not installed
    print(
        "ERROR: Npcap is not installed.",
        file=sys.stderr,
    )
    print(
        "Install Npcap from https://npcap.com (enable WinPcap API-compatible mode).",
        file=sys.stderr,
    )
    sys.exit(1)


def check_admin() -> None:
    """Verify the current process is running with administrator privileges.

    Uses ctypes to call the Windows shell32 IsUserAnAdmin() API.
    Falls back to exit(1) if the call itself raises an exception (defensive).

    Exits with code 1 and prints a clear error if not running as admin.
    Returns None if admin privileges are confirmed.

    Requirement: CAP-03
    """
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception as exc:
        logger.warning("Admin check raised an exception: %s", exc)
        is_admin = 0

    if not is_admin:
        print(
            "ERROR: PNPG requires administrator privileges.",
            file=sys.stderr,
        )
        print(
            "Right-click your terminal and select 'Run as administrator'.",
            file=sys.stderr,
        )
        sys.exit(1)
