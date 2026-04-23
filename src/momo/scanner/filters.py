"""
Filter chain — composable filters for scan execution.

Each filter takes a DataFrame and returns a filtered DataFrame.
Filters are chained: Universe → Price → Volume → ADR → Custom → Rank → Output.
"""

import logging
from abc import ABC, abstractmethod

import pandas as pd

logger = logging.getLogger(__name__)


class Filter(ABC):
    """Base class for all filters."""

    @abstractmethod
    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


class PriceFilter(Filter):
    """Filter by min/max price."""

    def __init__(self, min_price: float = 0, max_price: float = float("inf")):
        self.min_price = min_price
        self.max_price = max_price

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df[(df["close"] >= self.min_price) & (df["close"] <= self.max_price)]
        logger.debug(f"PriceFilter: {before} → {len(df)}")
        return df


class VolumeFilter(Filter):
    """Filter by min average volume and min dollar volume."""

    def __init__(self, min_avg_volume: int = 0, min_dollar_volume: float = 0):
        self.min_avg_volume = min_avg_volume
        self.min_dollar_volume = min_dollar_volume

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        if "avg_volume" in df.columns:
            df = df[df["avg_volume"] >= self.min_avg_volume]
        if "dollar_volume" in df.columns:
            df = df[df["dollar_volume"] >= self.min_dollar_volume]
        logger.debug(f"VolumeFilter: {before} → {len(df)}")
        return df


class ADRFilter(Filter):
    """Filter by ADR% range."""

    def __init__(self, min_adr: float = 0, max_adr: float = float("inf"), period: int = 20):
        self.min_adr = min_adr
        self.max_adr = max_adr
        self.period = period
        self.column = f"adr_pct_{period}"

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.column not in df.columns:
            logger.warning(f"ADRFilter: column '{self.column}' not found")
            return df
        before = len(df)
        df = df[(df[self.column] >= self.min_adr) & (df[self.column] <= self.max_adr)]
        logger.debug(f"ADRFilter: {before} → {len(df)}")
        return df


class TrendIntensityFilter(Filter):
    """Filter by Trend Intensity range."""

    def __init__(self, min_ti: float = 0, max_ti: float = float("inf")):
        self.min_ti = min_ti
        self.max_ti = max_ti

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if "trend_intensity" not in df.columns:
            logger.warning("TrendIntensityFilter: 'trend_intensity' column not found")
            return df
        before = len(df)
        df = df[(df["trend_intensity"] >= self.min_ti) & (df["trend_intensity"] <= self.max_ti)]
        logger.debug(f"TrendIntensityFilter: {before} → {len(df)}")
        return df


class RankFilter(Filter):
    """Filter by percentile rank — top N% or bottom N%."""

    def __init__(self, column: str, percentile: str = "top", threshold: float = 3.0):
        self.column = column
        self.percentile = percentile
        self.threshold = threshold

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.column not in df.columns:
            logger.warning(f"RankFilter: column '{self.column}' not found")
            return df

        before = len(df)
        df = df.dropna(subset=[self.column])

        if self.percentile == "top":
            cutoff = 100 - self.threshold
            df = df[df[self.column] >= cutoff]
        elif self.percentile == "bottom":
            df = df[df[self.column] <= self.threshold]

        logger.debug(f"RankFilter ({self.column} {self.percentile} {self.threshold}%): {before} → {len(df)}")
        return df


class UniverseFilter(Filter):
    """Filter by universe type (us_listed, adr, otc)."""

    def __init__(self, universe_type: str = "all"):
        self.universe_type = universe_type

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.universe_type == "all":
            return df
        if "universe" not in df.columns:
            logger.warning("UniverseFilter: 'universe' column not found")
            return df
        before = len(df)
        df = df[df["universe"] == self.universe_type]
        logger.debug(f"UniverseFilter ({self.universe_type}): {before} → {len(df)}")
        return df


class DailyChangeFilter(Filter):
    """Filter by minimum daily % change."""

    def __init__(self, min_change_pct: float = 0):
        self.min_change_pct = min_change_pct

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if "daily_change_pct" not in df.columns:
            logger.warning("DailyChangeFilter: 'daily_change_pct' column not found")
            return df
        before = len(df)
        df = df[df["daily_change_pct"] >= self.min_change_pct]
        logger.debug(f"DailyChangeFilter: {before} → {len(df)}")
        return df


class ExtensionFilter(Filter):
    """Filter by max % extension above SMA20 — avoids chasing extended stocks."""

    def __init__(self, max_pct_above_sma: float = 50.0, sma_period: int = 20):
        self.max_pct_above_sma = max_pct_above_sma
        self.sma_period = sma_period

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if "close" not in df.columns:
            logger.warning("ExtensionFilter: 'close' column not found")
            return df

        # Calculate SMA20 from the available data if not present
        sma_col = f"sma_{self.sma_period}"
        if sma_col not in df.columns:
            # We need price history to calculate SMA — skip if not available
            # The extension will be calculated in the indicator table
            logger.warning(f"ExtensionFilter: '{sma_col}' column not found — skipping")
            return df

        before = len(df)
        # Calculate % above SMA
        df = df.dropna(subset=[sma_col, "close"])
        df["pct_above_sma"] = ((df["close"] - df[sma_col]) / df[sma_col]) * 100
        df = df[df["pct_above_sma"] <= self.max_pct_above_sma]
        df = df.drop(columns=["pct_above_sma"])
        logger.debug(f"ExtensionFilter (max {self.max_pct_above_sma}% above SMA{self.sma_period}): {before} → {len(df)}")
        return df


class FilterChain:
    """Executes a sequence of filters."""

    def __init__(self, filters: list[Filter]):
        self.filters = filters

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        for f in self.filters:
            df = f.apply(df)
            if df.empty:
                logger.info(f"{f.name} returned 0 results — chain stopped early")
                break
        return df
