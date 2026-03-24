"""
Configuration Utilities

Handles loading and parsing YAML configuration files.
"""

from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: str = "config.yaml") -> dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path.absolute()}")

    with open(path, 'r') as f:
        config = yaml.safe_load(f)

    return config


def get_default_config() -> dict[str, Any]:
    """
    Return default configuration if no file is available.

    Returns:
        Default configuration dictionary
    """
    return {
        "simulation": {
            "tick_interval": 5.0,
            "startup_jitter_max": 5.0,
            "outside_temperature": 15.0
        },
        "building": {
            "id": "b01",
            "floors": 10,
            "rooms_per_floor": 20
        },
        "mqtt": {
            "broker_host": "localhost",
            "broker_port": 1883,
            "client_id_prefix": "world_engine",
            "topic_prefix": "campus"
        },
        "database": {
            "path": "world_engine.db"
        },
        "physics": {
            "k_env": 0.01,
            "k_hvac": 0.2
        }
    }
