"""Tests for pnpg.prereqs — CAP-02 (Npcap check) and CAP-03 (admin check)."""
import pytest
from pnpg.prereqs import check_npcap, check_admin


def test_npcap_check_exits(mock_npcap_missing):
    """When Npcap directory does not exist (mocked), check_npcap() calls sys.exit(1)."""
    with pytest.raises(SystemExit) as exc_info:
        check_npcap()
    assert exc_info.value.code == 1


def test_npcap_check_passes(mock_npcap_present):
    """When Npcap directory exists (mocked), check_npcap() returns None."""
    result = check_npcap()
    assert result is None


def test_admin_check_exits(mock_not_admin):
    """When IsUserAnAdmin returns 0 (mocked), check_admin() calls sys.exit(1)."""
    with pytest.raises(SystemExit) as exc_info:
        check_admin()
    assert exc_info.value.code == 1


def test_admin_check_passes(mock_admin):
    """When IsUserAnAdmin returns 1 (mocked), check_admin() returns None."""
    result = check_admin()
    assert result is None
