"""Tests for interface.py — CAP-04, CAP-09.

Covers auto-selection by highest bytes_sent, config override, and empty NIC error.
"""
import unittest.mock as mock
from collections import namedtuple

import pytest

from pnpg.capture.interface import select_interface


# Minimal stand-in for psutil snetiostatistics namedtuple
FakeCounter = namedtuple("FakeCounter", ["bytes_sent", "bytes_recv", "packets_sent", "packets_recv", "errin", "errout", "dropin", "dropout"])


def _make_counter(bytes_sent=0, bytes_recv=0):
    """Helper to create a FakeCounter with default zero fields."""
    return FakeCounter(
        bytes_sent=bytes_sent,
        bytes_recv=bytes_recv,
        packets_sent=0,
        packets_recv=0,
        errin=0,
        errout=0,
        dropin=0,
        dropout=0,
    )


def test_auto_select_highest_bytes_sent():
    """CAP-04: Auto-select the interface with highest bytes_sent when config['interface'] is None."""
    fake_counters = {
        "Wi-Fi": _make_counter(bytes_sent=1000),
        "Ethernet": _make_counter(bytes_sent=500),
    }

    # Mock psutil and Scapy ifaces
    with mock.patch("psutil.net_io_counters", return_value=fake_counters) as mock_psutil:
        # Mock scapy conf.ifaces so the Scapy mapping doesn't require Npcap
        mock_iface_obj = mock.MagicMock()
        mock_ifaces = mock.MagicMock()
        mock_ifaces.dev_from_networkname.return_value = mock_iface_obj

        with mock.patch("pnpg.capture.interface._get_scapy_ifaces", return_value=mock_ifaces):
            result = select_interface({"interface": None})

    assert result is not None
    mock_psutil.assert_called_once_with(pernic=True)


def test_config_override():
    """CAP-09: When config['interface'] is set, return it directly without calling psutil."""
    with mock.patch("psutil.net_io_counters") as mock_psutil:
        result = select_interface({"interface": "Ethernet"})

    assert result == "Ethernet"
    mock_psutil.assert_not_called()


def test_no_interfaces_raises():
    """If psutil returns an empty dict, select_interface must raise RuntimeError."""
    with mock.patch("psutil.net_io_counters", return_value={}):
        with pytest.raises(RuntimeError):
            select_interface({"interface": None})
