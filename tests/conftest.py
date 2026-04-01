"""Shared pytest fixtures for PNPG test suite."""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


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
