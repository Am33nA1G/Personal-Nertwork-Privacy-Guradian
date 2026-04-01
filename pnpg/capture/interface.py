"""Interface auto-selection and psutil-to-Scapy name mapping.

CAP-04: Auto-select the network interface with the highest outbound bytes_sent
        when no interface is specified in config or CLI.
CAP-09: Accept a config override — if config['interface'] is set, use it
        directly without calling psutil.

Windows caveat: psutil reports friendly names like "Wi-Fi" or "Ethernet".
Scapy on Windows uses GUID-based names like \\Device\\NPF_{GUID-...}.
conf.ifaces.dev_from_networkname() resolves the friendly name to the Scapy
interface object. If mapping fails we fall back to the friendly name and let
Scapy raise an informative error at sniff() time.
"""
import logging

import psutil


logger = logging.getLogger(__name__)


def _get_scapy_ifaces():
    """Return scapy.config.conf.ifaces for interface name resolution.

    Isolated into its own function so tests can mock it without importing Scapy
    at module level (Scapy import requires Npcap on Windows).
    """
    from scapy.config import conf  # pylint: disable=import-outside-toplevel

    return conf.ifaces


def select_interface(config: dict) -> str:
    """Return the network interface name to pass to Scapy's sniff().

    CAP-09: If config['interface'] is not None, return that value immediately
    without touching psutil — honours explicit user override.

    CAP-04: Otherwise, query psutil.net_io_counters(pernic=True) to find the
    interface with the highest bytes_sent, then attempt to resolve its friendly
    name to a Scapy GUID-based name via conf.ifaces.dev_from_networkname().

    Args:
        config: Config dict (from load_config()). Must contain 'interface' key.

    Returns:
        Interface name string suitable for Scapy's sniff(iface=...).

    Raises:
        RuntimeError: If psutil reports no network interfaces.
    """
    override = config.get("interface")
    if override is not None:
        logger.info("Interface override from config: %s", override)
        return override

    counters = psutil.net_io_counters(pernic=True)
    if not counters:
        raise RuntimeError("No network interfaces found via psutil")

    # Pick the busiest interface by outbound bytes (CAP-04)
    best_name, best_stats = max(counters.items(), key=lambda item: item[1].bytes_sent)
    logger.info(
        "Auto-selected interface: %s (bytes_sent: %d)", best_name, best_stats.bytes_sent
    )

    # Attempt psutil friendly name → Scapy GUID name mapping (Windows)
    try:
        ifaces = _get_scapy_ifaces()
        scapy_iface = ifaces.dev_from_networkname(best_name)
        return scapy_iface
    except Exception:
        logger.warning(
            "Could not map '%s' to Scapy interface name, using as-is", best_name
        )
        return best_name
