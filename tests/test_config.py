"""Tests for pnpg.config — CONFIG-01 (defaults) and CONFIG-02 (overrides/validation)."""
import logging
import pytest
from pathlib import Path
from pnpg.config import load_config, DEFAULT_CONFIG


def test_defaults(tmp_path: Path):
    """When config.yaml does not exist, load_config() returns all DEFAULT_CONFIG keys with correct defaults."""
    config = load_config(str(tmp_path / "nonexistent.yaml"))
    assert isinstance(config, dict)
    # All DEFAULT_CONFIG keys must be present
    for key in DEFAULT_CONFIG:
        assert key in config, f"Missing key: {key}"
    # Spot-check specific defaults
    assert config["queue_size"] == 500
    assert config["debug_mode"] is False
    assert config["interface"] is None
    assert config["poll_interval_ms"] == 200


def test_config_override(tmp_path: Path):
    """When config.yaml has queue_size: 100, load_config() returns queue_size=100 with other keys at defaults."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("queue_size: 100\n")
    config = load_config(str(config_file))
    assert config["queue_size"] == 100
    assert config["debug_mode"] is False  # Default preserved


def test_unknown_key_ignored(tmp_path: Path, caplog):
    """When config.yaml has an unknown key, load_config() ignores it and logs a warning."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("bogus_key: 42\n")
    with caplog.at_level(logging.WARNING):
        config = load_config(str(config_file))
    assert "bogus_key" not in config
    assert "Unknown config key" in caplog.text


def test_invalid_yaml(tmp_path: Path, caplog):
    """When config.yaml contains invalid YAML, load_config() returns all defaults and logs a warning."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("{{{invalid\n")
    with caplog.at_level(logging.WARNING):
        config = load_config(str(config_file))
    assert config == DEFAULT_CONFIG
    assert "parse error" in caplog.text
