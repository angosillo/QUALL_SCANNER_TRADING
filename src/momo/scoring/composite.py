"""
Composite scoring engine (0-100).

Qullamaggie doesn't use numeric scoring — he reviews charts visually.
This is a COMPLEMENTARY feature for prioritizing results without his experience.

Score = w1*Momentum + w2*TrendStrength + w3*VolumeProfile + w4*Volatility + w5*RS
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def normalize_series(series: pd.Series, min_val: float = 0, max_val: float = 100) -> pd.Series:
    """Normalize a series to 0-100 range."""
    if series.empty or series.isna().all():
        return series
    s_min = series.min()
    s_max = series.max()
    if s_max == s_min:
        return pd.Series(50, index=series.index)
    normalized = (series - s_min) / (s_max - s_min) * 100
    return normalized.clip(0, 100)


def calculate_composite_score(
    df: pd.DataFrame,
    weights: dict | None = None,
) -> pd.DataFrame:
    """
    Calculate composite score 0-100 for each stock.

    Components:
        - Momentum (30%): percentile rank of price growth
        - TrendStrength (25%): normalized TI (100→0, 120→100)
        - VolumeProfile (20%): today's vol / 20d avg vol
        - Volatility (15%): normalized ADR%
        - RelativeStrength (10%): stock vs SPY

    Args:
        df: DataFrame with indicator columns
        weights: Dict with weight values (optional, uses defaults)

    Returns:
        DataFrame with added composite_score column
    """
    df = df.copy()

    # Default weights
    w = {
        "momentum": 0.30,
        "trend": 0.25,
        "volume": 0.20,
        "volatility": 0.15,
        "relative_strength": 0.10,
    }
    if weights:
        w.update({k: v for k, v in weights.items() if k in w})

    scores = pd.DataFrame(index=df.index)

    # 1. Momentum: use best available rank
    rank_cols = ["rank_1m", "rank_3m", "rank_6m"]
    for col in rank_cols:
        if col in df.columns:
            scores["momentum"] = df[col].fillna(50)
            break
    if "momentum" not in scores.columns:
        scores["momentum"] = 50

    # 2. Trend Strength: normalize TI (100→0, 120→100)
    if "trend_intensity" in df.columns:
        ti = df["trend_intensity"].fillna(100)
        scores["trend"] = ((ti - 100) / 20 * 100).clip(0, 100)
    else:
        scores["trend"] = 50

    # 3. Volume Profile: today's volume / avg volume
    if "volume" in df.columns and "avg_volume" in df.columns:
        vol_ratio = (df["volume"] / df["avg_volume"].replace(0, np.nan)).fillna(1)
        scores["volume"] = normalize_series(vol_ratio)
    else:
        scores["volume"] = 50

    # 4. Volatility: normalized ADR%
    adr_col = "adr_pct_20" if "adr_pct_20" in df.columns else "adr_pct_10"
    if adr_col in df.columns:
        scores["volatility"] = normalize_series(df[adr_col].fillna(0))
    else:
        scores["volatility"] = 50

    # 5. Relative Strength (simplified — use growth_1m if available)
    if "growth_1m" in df.columns:
        scores["relative_strength"] = normalize_series(df["growth_1m"].fillna(0))
    else:
        scores["relative_strength"] = 50

    # Weighted sum
    composite = (
        w["momentum"] * scores["momentum"]
        + w["trend"] * scores["trend"]
        + w["volume"] * scores["volume"]
        + w["volatility"] * scores["volatility"]
        + w["relative_strength"] * scores["relative_strength"]
    )

    df["composite_score"] = composite.round(1)

    # Also store component scores for transparency
    for col in scores.columns:
        df[f"score_{col}"] = scores[col].round(1)

    return df
