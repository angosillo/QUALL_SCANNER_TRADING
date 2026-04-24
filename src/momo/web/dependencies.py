"""Shared dependencies for web routes."""

import logging
from pathlib import Path
from typing import Any

import tomli

logger = logging.getLogger(__name__)


def get_db_path() -> str:
    """Get database path from config or default."""
    config_path = Path("config/settings.toml")
    if config_path.exists():
        with open(config_path, "rb") as f:
            config = tomli.load(f)
        db_path = config.get("general", {}).get("db_path", "data/momo.db")
        return str(config_path.parent / db_path)
    return str(Path.cwd() / "data" / "momo.db")


def load_web_config() -> dict[str, Any]:
    """Load web section from settings.toml."""
    config_path = Path("config/settings.toml")
    defaults = {
        "host": "0.0.0.0",
        "port": 8000,
        "title": "MOMO Scanner",
        "theme": "dark",
        "results_page_size": 50,
        "chart_days": 120,
        "chart_smas": [20, 50, 200],
    }
    if not config_path.exists():
        return defaults
    with open(config_path, "rb") as f:
        config = tomli.load(f)
    web_cfg = config.get("web", {})
    return {**defaults, **web_cfg}
