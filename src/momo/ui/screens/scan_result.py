"""
Scan result screen — displays results for a selected scan.
"""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static

from ...scanner.loader import load_all_scans
from ...scanner.engine import run_scan, build_indicator_table
from ..widgets.result_table import ResultTable
from ...watchlist.manager import list_watchlists

logger = logging.getLogger(__name__)


class ScanResultScreen(Screen):
    """Screen showing results of a single scan."""

    BINDINGS = [
        Binding("enter", "open_symbol", "Detail"),
        Binding("a", "add_to_watchlist", "Add to WL"),
        Binding("s", "toggle_sort", "Sort"),
        Binding("e", "export_csv", "Export CSV"),
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, db_path: str, scan_id: str) -> None:
        super().__init__()
        self.db_path = db_path
        self.scan_id = scan_id
        self.scan_config: dict | None = None
        self.results_df: pd.DataFrame = pd.DataFrame()
        self._status = Static("Cargando...", id="status")
        self._filter_input = Input(placeholder="Filtrar por símbolo...", id="filter_input")

    def compose(self):
        yield Header()
        yield self._status
        yield self._filter_input
        yield Vertical(ResultTable(), id="results-container")
        yield Footer()

    def on_mount(self) -> None:
        self._load_results()

    def _load_results(self) -> None:
        scans = load_all_scans("config/scans")
        self.scan_config = next((s for s in scans if s["scan"]["id"] == self.scan_id), None)
        if self.scan_config is None:
            self._status.update(f"Scan '{self.scan_id}' no encontrado")
            return

        name = self.scan_config["scan"]["name"]

        # Try loading from DB history first
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT * FROM scan_results
                WHERE scan_id = ? AND run_date = (
                    SELECT MAX(run_date) FROM scan_results WHERE scan_id = ?
                )
                ORDER BY rank_in_scan
            """
            df = pd.read_sql(query, conn, params=(self.scan_id, self.scan_id))
            conn.close()
        except Exception as exc:
            logger.warning(f"Could not load from DB: {exc}")
            df = pd.DataFrame()

        if df.empty:
            # Run scan on the fly
            self._status.update(f"Ejecutando {name}...")
            try:
                indicator_table = build_indicator_table(self.db_path)
                if indicator_table.empty:
                    self._status.update("No hay datos de indicadores")
                    return
                df = run_scan(self.scan_config, indicator_table, self.db_path)
            except Exception as exc:
                logger.error(f"Scan execution failed: {exc}")
                self._status.update(f"Error ejecutando scan: {exc}")
                return

        self.results_df = df
        display_cfg = self.scan_config.get("display", {})
        fields = display_cfg.get("fields", ["symbol", "close", "volume"])
        table = self.query_one(ResultTable)
        table.load_results(df, fields)
        self._status.update(f"{name} — {len(df)} resultados")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter results as user types."""
        query = event.value.strip()
        table = self.query_one(ResultTable)
        if query:
            table.filter_by_symbol(query)
        else:
            display_cfg = self.scan_config.get("display", {}) if self.scan_config else {}
            fields = display_cfg.get("fields", ["symbol", "close", "volume"])
            table.load_results(self.results_df, fields)

    def action_open_symbol(self) -> None:
        table = self.query_one(ResultTable)
        symbol = table.get_selected_symbol()
        if symbol:
            from .symbol_detail import SymbolDetailScreen
            self.app.push_screen(SymbolDetailScreen(self.db_path, symbol))
        else:
            self.notify("Selecciona un símbolo", severity="warning")

    def action_toggle_sort(self) -> None:
        table = self.query_one(ResultTable)
        table.toggle_sort()

    def action_export_csv(self) -> None:
        if self.results_df.empty or self.scan_config is None:
            self.notify("No hay resultados para exportar", severity="warning")
            return
        export_dir = Path("data/exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        scan_id = self.scan_config["scan"]["id"]
        csv_path = export_dir / f"{date_str}_{scan_id}.csv"
        self.results_df.to_csv(csv_path, index=False)
        self.notify(f"Exportado: {csv_path}")

    def action_add_to_watchlist(self) -> None:
        table = self.query_one(ResultTable)
        symbol = table.get_selected_symbol()
        if not symbol:
            self.notify("Selecciona un símbolo", severity="warning")
            return
        try:
            wls = list_watchlists(self.db_path)
            if wls.empty:
                self.notify("No hay watchlists. Crea una primero (pantalla Watchlists).", severity="warning")
                return
            # Show simple selection via notify for now
            options = "\n".join([f"{r['id']}: {r['name']}" for _, r in wls.iterrows()])
            self.notify(f"Añadir {symbol} a:\n{options}\n\nUsa CLI: python -m momo watchlist add <nombre> {symbol}")
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error")

    def action_go_back(self) -> None:
        self.app.pop_screen()
