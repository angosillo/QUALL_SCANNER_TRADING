"""
Scan config loader — reads TOML scan definitions and builds filter chains.
"""

import logging
from pathlib import Path

import tomli

from .filters import (
    ADRFilter,
    DailyChangeFilter,
    ExtensionFilter,
    Filter,
    PriceFilter,
    RankFilter,
    TrendIntensityFilter,
    UniverseFilter,
    VolumeFilter,
)

logger = logging.getLogger(__name__)


def load_scan_config(path: str) -> dict:
    """Load a single scan TOML config file."""
    with open(path, "rb") as f:
        return tomli.load(f)


def load_all_scans(config_dir: str) -> list[dict]:
    """Load all scan configs from a directory."""
    config_path = Path(config_dir)
    scans = []

    for toml_file in sorted(config_path.glob("*.toml")):
        try:
            config = load_scan_config(str(toml_file))
            config["_file"] = str(toml_file)
            scans.append(config)
            logger.info(f"Loaded scan: {config['scan']['name']} ({config['scan']['id']})")
        except Exception as e:
            logger.error(f"Failed to load {toml_file}: {e}")

    return scans


def build_filters(scan_config: dict) -> list[Filter]:
    """Build a list of Filter objects from a scan config dict."""
    filters = []
    f = scan_config.get("filters", {})

    # Universe filter
    universe_cfg = scan_config.get("universe", {})
    universe_type = universe_cfg.get("type", "all")
    if universe_type != "all":
        filters.append(UniverseFilter(universe_type))

    # Price filter
    if "price" in f:
        filters.append(PriceFilter(
            min_price=f["price"].get("min", 0),
            max_price=f["price"].get("max", float("inf")),
        ))

    # Volume filter
    if "volume" in f:
        filters.append(VolumeFilter(
            min_avg_volume=f["volume"].get("min_avg_volume", 0),
            min_dollar_volume=f["volume"].get("min_dollar_volume", 0),
        ))

    # ADR filter
    if "adr_percent" in f:
        filters.append(ADRFilter(
            min_adr=f["adr_percent"].get("min", 0),
            max_adr=f["adr_percent"].get("max", float("inf")),
            period=f["adr_percent"].get("period", 20),
        ))

    # Trend Intensity filter
    if "trend_intensity" in f:
        filters.append(TrendIntensityFilter(
            min_ti=f["trend_intensity"].get("min", 0),
            max_ti=f["trend_intensity"].get("max", float("inf")),
        ))

    # Rank filter
    if "rank" in f:
        rank_cfg = f["rank"]
        period_days = rank_cfg.get("period_days", 21)
        # Map period_days to column name (matching price_rank.calculate_all_ranks keys)
        period_map = {5: "rank_5d", 21: "rank_1m", 63: "rank_3m", 126: "rank_6m", 252: "rank_1y", 504: "rank_2y"}
        column = period_map.get(period_days)
        if column is None:
            # Fallback: convert days to approximate label
            if period_days >= 500:
                column = f"rank_{period_days // 252}y"
            elif period_days >= 200:
                column = "rank_1y"
            else:
                column = f"rank_{period_days}d"

        filters.append(RankFilter(
            column=column,
            percentile=rank_cfg.get("percentile", "top"),
            threshold=rank_cfg.get("threshold", 3.0),
        ))

    # Extension filter (avoid extended stocks)
    if "extension" in f:
        filters.append(ExtensionFilter(
            max_pct_above_sma=f["extension"].get("max_pct_above_sma20", 50.0),
            sma_period=20,
        ))

    # Daily change filter (for intraday scans)
    if "daily_change" in f:
        filters.append(DailyChangeFilter(
            min_change_pct=f["daily_change"].get("min_pct", 0),
        ))

    return filters
