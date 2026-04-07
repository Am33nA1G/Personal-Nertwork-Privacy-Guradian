"""Configuration loader for PNPG.

Loads config.yaml, merges with DEFAULT_CONFIG, warns on unknown keys,
and handles missing/invalid YAML gracefully.

CONFIG-01: All thresholds live in config.yaml with documented defaults.
CONFIG-02: Config validated at startup; invalid/missing keys do not crash startup.
"""
import logging
import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict = {
    "queue_size": 500,
    "poll_interval_ms": 200,
    "alert_rate_limit_per_sec": 1,
    "port_allowlist": [80, 443, 53, 123, 5353, 8080, 8443],
    "log_rotation_size_mb": 50,
    "debug_mode": False,
    "interface": None,
    "connection_rate_threshold": 50,
    "dns_cache_size": 1000,
    "dns_cache_ttl_sec": 300,
    "proc_cache_ttl_sec": 2,
    "log_dir": "logs",
    "geoip_country_db": "data/GeoLite2-Country.mmdb",
    "geoip_asn_db": "data/GeoLite2-ASN.mmdb",
    "blocklist_path": "data/blocklist.txt",
    "connection_rate_threshold_per_min": 100,
    "tor_exit_list_path": "data/tor-exit-nodes.txt",
    "known_processes": [
        "chrome.exe",
        "firefox.exe",
        "msedge.exe",
        "explorer.exe",
        "svchost.exe",
        "System",
        "python.exe",
        "node.exe",
        "code.exe",
    ],
    "db_dsn": "postgresql://pnpg:pnpg@localhost:5432/pnpg",
    "db_pool_min": 2,
    "db_pool_max": 10,
    "jwt_secret": "",
    "jwt_expiry_hours": 8,
    "ws_batch_interval_ms": 500,
    "ws_max_batch_size": 100,
    "ws_heartbeat_interval_s": 10,
    "ndjson_max_size_mb": 100,
    "retention_connections_days": 30,
    "retention_alerts_days": 90,
    "purge_schedule_hour": 2,
    "api_rate_limit": "100/minute",
    "auth_file": "data/auth.json",
}


def load_config(path: str = "config.yaml") -> dict:
    """Load PNPG configuration from a YAML file, merged with defaults.

    Behaviour:
    - File not found: log INFO, return all defaults.
    - Invalid YAML: log WARNING (parse error), return all defaults.
    - Unknown keys in file: log WARNING per key, ignore the key.
    - Known keys in file: override the default value.

    The returned dict is always a NEW dict — DEFAULT_CONFIG is never mutated.

    Args:
        path: Path to the config YAML file. Defaults to "config.yaml".

    Returns:
        A dict containing all DEFAULT_CONFIG keys with any user overrides applied.

    Requirements: CONFIG-01, CONFIG-02
    """
    user_config: dict = {}

    try:
        with open(path, "r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
            if isinstance(loaded, dict):
                user_config = loaded
            # yaml.safe_load returns None for an empty file — treat as empty dict
    except FileNotFoundError:
        logger.info("config.yaml not found at '%s' -- using all defaults", path)
    except yaml.YAMLError as exc:
        logger.warning(
            "config.yaml parse error at '%s': %s -- using all defaults", path, exc
        )
        return dict(DEFAULT_CONFIG)

    # Build a new dict from defaults (immutable — never mutate DEFAULT_CONFIG)
    merged: dict = dict(DEFAULT_CONFIG)

    for key, value in user_config.items():
        if key in DEFAULT_CONFIG:
            merged[key] = value
        else:
            logger.warning("Unknown config key ignored: %s", key)

    return merged
