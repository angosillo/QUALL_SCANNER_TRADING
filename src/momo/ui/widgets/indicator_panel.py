"""
Indicator panel widget — displays symbol indicators.
"""

import pandas as pd
from rich.text import Text
from textual.widgets import Static


class IndicatorPanel(Static):
    """Panel displaying current indicators for a symbol."""

    def __init__(self) -> None:
        super().__init__(id="indicator_panel")
        self._df: pd.DataFrame | None = None

    def update_data(self, df: pd.DataFrame) -> None:
        """Update panel with indicator data."""
        self._df = df.copy() if not df.empty else None
        self._render_content()

    def _render_content(self) -> None:
        if self._df is None or self._df.empty:
            self.update("No data available")
            return

        row = self._df.iloc[0]
        text = Text()
        text.append("Indicadores\n", style="bold underline")
        text.append("─" * 40 + "\n")

        cols = [
            ("Símbolo", "symbol"),
            ("Close", "close"),
            ("Volume", "volume"),
            ("ADR% 20d", "adr_pct_20"),
            ("Trend Intensity", "trend_intensity"),
            ("Composite Score", "composite_score"),
            ("Score Momentum", "score_momentum"),
            ("Score Trend", "score_trend"),
            ("Score Volume", "score_volume"),
            ("Score Volatility", "score_volatility"),
            ("Score RS", "score_relative_strength"),
            ("Growth 5d", "price_growth_5d"),
            ("Growth 1m", "price_growth_1m"),
            ("Growth 3m", "price_growth_3m"),
            ("Growth 6m", "price_growth_6m"),
            ("Growth 1y", "price_growth_1y"),
            ("Rank 5d", "rank_5d"),
            ("Rank 1m", "rank_1m"),
            ("Rank 3m", "rank_3m"),
            ("Rank 6m", "rank_6m"),
            ("Rank 1y", "rank_1y"),
        ]

        for label, key in cols:
            if key in row and pd.notna(row[key]):
                val = row[key]
                if isinstance(val, float):
                    val = f"{val:.2f}"
                text.append(f"{label:20s}: ", style="dim")
                text.append(f"{val}\n", style="bold")

        self.update(text)
