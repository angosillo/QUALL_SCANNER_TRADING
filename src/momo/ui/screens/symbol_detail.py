"""
Symbol detail screen — indicators, ASCII chart, and historical prices.
"""

import logging

import pandas as pd
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from ...charts.candlestick import render_ascii_candles
from ...data.ingest import get_connection
from ..widgets.indicator_panel import IndicatorPanel
from ...watchlist.manager import list_watchlists, add_symbol

logger = logging.getLogger(__name__)


class SymbolDetailScreen(Screen):
    """Screen showing detailed info for a single symbol."""

    BINDINGS = [
        Binding("a", "add_to_watchlist", "Add to WL"),
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, db_path: str, symbol: str) -> None:
        super().__init__()
        self.db_path = db_path
        self.symbol = symbol
        self._chart = Static(id="ascii_chart")
        self._history_table = DataTable(id="history_table")
        self._indicator_panel = IndicatorPanel()
        self._status = Static(f"{symbol}", id="status")

    def compose(self):
        yield Header()
        yield self._status
        with Horizontal():
            with Vertical(id="left-panel"):
                yield self._indicator_panel
            with Vertical(id="right-panel"):
                yield self._chart
                yield self._history_table
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        conn = get_connection(self.db_path)
        try:
            # Latest indicators
            indicators_df = pd.read_sql(
                """
                SELECT * FROM indicators
                WHERE symbol = ?
                ORDER BY date DESC
                LIMIT 1
                """,
                conn,
                params=(self.symbol,),
            )
            self._indicator_panel.update_data(indicators_df)

            # Historical prices (last 60 for chart, last 20 for table)
            prices_df = pd.read_sql(
                """
                SELECT date, open, high, low, close, volume
                FROM daily_prices
                WHERE symbol = ?
                ORDER BY date DESC
                LIMIT 60
                """,
                conn,
                params=(self.symbol,),
            )
            prices_df = prices_df.sort_values("date")

            # ASCII chart
            try:
                chart_text = render_ascii_candles(prices_df, self.symbol, days=60, width=60, height=16)
                self._chart.update(chart_text)
            except Exception as exc:
                logger.warning(f"ASCII chart failed: {exc}")
                self._chart.update("No se pudo generar gráfico ASCII")

            # History table (last 20)
            history = prices_df.tail(20).sort_values("date", ascending=False)
            self._history_table.clear(columns=True)
            self._history_table.add_columns("Date", "Open", "High", "Low", "Close", "Volume")
            for _, row in history.iterrows():
                self._history_table.add_row(
                    str(row["date"]),
                    f"{row['open']:.2f}",
                    f"{row['high']:.2f}",
                    f"{row['low']:.2f}",
                    f"{row['close']:.2f}",
                    f"{int(row['volume'])}",
                )
        except Exception as exc:
            logger.error(f"Error loading symbol detail: {exc}")
            self._status.update(f"Error cargando {self.symbol}: {exc}")
        finally:
            conn.close()

    def action_add_to_watchlist(self) -> None:
        try:
            wls = list_watchlists(self.db_path)
            if wls.empty:
                self.notify("No hay watchlists. Crea una primero.", severity="warning")
                return
            # Add to first watchlist for simplicity in TUI
            wl_id = int(wls.iloc[0]["id"])
            add_symbol(self.db_path, wl_id, self.symbol)
            self.notify(f"{self.symbol} añadido a '{wls.iloc[0]['name']}'")
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error")

    def action_go_back(self) -> None:
        self.app.pop_screen()
