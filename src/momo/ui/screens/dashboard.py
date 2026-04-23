"""
Dashboard screen — lists all configured scans and their latest results.
"""

import logging

import pandas as pd
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ...scanner.loader import load_all_scans
from ...scanner.engine import run_all_scans, build_indicator_table
from ..widgets.scan_table import ScanTable

logger = logging.getLogger(__name__)


class DashboardScreen(Screen):
    """Main dashboard showing all scans."""

    BINDINGS = [
        Binding("r", "run_scans", "Run all"),
        Binding("w", "goto_watchlists", "Watchlists"),
        Binding("enter", "open_scan", "Open scan"),
    ]

    def __init__(self, db_path: str) -> None:
        super().__init__()
        self.db_path = db_path
        self.scans: list[dict] = []
        self._status = Static("Cargando scans...", id="status")

    def compose(self):
        yield Header(show_clock=True)
        yield self._status
        yield Vertical(ScanTable(), id="dashboard-container")
        yield Footer()

    def on_mount(self) -> None:
        self._load_dashboard()

    def _load_dashboard(self) -> None:
        self.scans = load_all_scans("config/scans")
        result_counts = self._get_result_counts()
        table = self.query_one(ScanTable)
        table.load_scans(self.scans, result_counts)
        self._status.update(f"Scans cargados: {len(self.scans)}")

    def _get_result_counts(self) -> dict[str, int]:
        """Get latest result count per scan from DB."""
        import sqlite3
        counts = {}
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT scan_id, COUNT(*) as c
                FROM scan_results
                WHERE run_date = (
                    SELECT MAX(run_date) FROM scan_results sr2 WHERE sr2.scan_id = scan_results.scan_id
                )
                GROUP BY scan_id
            """
            df = pd.read_sql(query, conn)
            counts = dict(zip(df["scan_id"], df["c"]))
            conn.close()
        except Exception as exc:
            logger.warning(f"Could not load result counts: {exc}")
        return counts

    def action_run_scans(self) -> None:
        """Re-run all enabled scans."""
        self._status.update("Ejecutando scans... (puede tardar)")
        self.run_worker(self._run_scans_worker(), exclusive=True)

    async def _run_scans_worker(self) -> None:
        try:
            indicator_table = build_indicator_table(self.db_path)
            if indicator_table.empty:
                self.notify("No hay datos de indicadores. Ejecuta 'download' primero.", severity="warning")
                self._status.update("Sin datos de indicadores")
                return
            run_all_scans(self.db_path, "config/scans", indicator_table)
            self._status.update("Scans completados")
            self._load_dashboard()
            self.notify("Scans re-ejecutados correctamente")
        except Exception as exc:
            logger.error(f"Scan run failed: {exc}")
            self.notify(f"Error ejecutando scans: {exc}", severity="error")
            self._status.update("Error en scans")

    def action_open_scan(self) -> None:
        """Open selected scan results."""
        table = self.query_one(ScanTable)
        scan_id = table.get_selected_scan_id()
        if scan_id:
            from .scan_result import ScanResultScreen
            self.app.push_screen(ScanResultScreen(self.db_path, scan_id))
        else:
            self.notify("Selecciona un scan primero", severity="warning")

    def action_goto_watchlists(self) -> None:
        """Navigate to watchlists screen."""
        from .watchlist import WatchlistScreen
        self.app.push_screen(WatchlistScreen(self.db_path))
