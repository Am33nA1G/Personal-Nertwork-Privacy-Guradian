"""Shared pytest fixtures for PNPG test suite."""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Provide a stub winreg module on non-Windows platforms so that
# pnpg.prereqs (and modules importing it) can be loaded in the Linux CI.
if "winreg" not in sys.modules:
    _winreg_stub = MagicMock()
    _winreg_stub.HKEY_LOCAL_MACHINE = 0x80000002
    sys.modules["winreg"] = _winreg_stub


@pytest.fixture
def tmp_config_path(tmp_path: Path) -> Path:
    """Return a Path for a temporary config.yaml (does not create the file)."""
    return tmp_path / "config.yaml"


@pytest.fixture
def mock_npcap_missing():
    """Patch filesystem and registry so Npcap appears NOT installed."""
    npcap_system32 = os.path.join(
        os.environ.get("WINDIR", "C:\\Windows"), "System32", "Npcap"
    )

    def fake_isdir(path):
        if path == npcap_system32:
            return False
        return os.path.isdir.__wrapped__(path) if hasattr(os.path.isdir, "__wrapped__") else False

    with patch("os.path.isdir", side_effect=lambda p: False), \
         patch("winreg.OpenKey", side_effect=FileNotFoundError("Npcap not found")):
        yield


@pytest.fixture
def mock_npcap_present():
    """Patch filesystem so Npcap System32 directory appears present."""
    npcap_system32 = os.path.join(
        os.environ.get("WINDIR", "C:\\Windows"), "System32", "Npcap"
    )

    def fake_isdir(path):
        if path == npcap_system32:
            return True
        return True

    with patch("os.path.isdir", side_effect=fake_isdir):
        yield


@pytest.fixture
def mock_admin():
    """Patch ctypes so IsUserAnAdmin returns 1 (admin)."""
    with patch("ctypes.windll") as mock_windll:
        mock_windll.shell32.IsUserAnAdmin.return_value = 1
        yield mock_windll


@pytest.fixture
def mock_not_admin():
    """Patch ctypes so IsUserAnAdmin returns 0 (not admin)."""
    with patch("ctypes.windll") as mock_windll:
        mock_windll.shell32.IsUserAnAdmin.return_value = 0
        yield mock_windll


@pytest.fixture
def detector_state():
    from pnpg.pipeline.detector import DetectorState

    return DetectorState()


@pytest.fixture
def enriched_event():
    return {
        "process_name": "chrome.exe",
        "pid": 1234,
        "dst_ip": "93.184.216.34",
        "dst_hostname": "example.com",
        "dst_port": 443,
        "protocol": "TCP",
        "src_ip": "192.168.1.5",
        "src_port": 52341,
        "threat_intel": {"is_blocklisted": False, "source": None},
        "dst_country": "US",
        "dst_asn": "AS15169",
        "dst_org": "Google LLC",
    }
