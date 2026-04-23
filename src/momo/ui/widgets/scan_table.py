"""
Scan table widget — displays configured scans.
"""

from textual.widgets import DataTable


class ScanTable(DataTable):
    """DataTable showing scan configurations."""

    def __init__(self) -> None:
        super().__init__(id="scan_table")
        self.cursor_type = "row"
        self.add_columns(
            "Nombre",
            "ID",
            "Side",
            "Freq",
            "Enabled",
            "Resultados",
        )

    def load_scans(self, scans: list[dict], result_counts: dict[str, int]) -> None:
        """Populate table with scan configs and result counts."""
        self.clear()
        for scan in scans:
            info = scan["scan"]
            scan_id = info["id"]
            count = result_counts.get(scan_id, 0)
            self.add_row(
                info.get("name", scan_id),
                scan_id,
                info.get("side", "-"),
                info.get("frequency", "-"),
                "✓" if info.get("enabled", True) else "✗",
                str(count),
                key=scan_id,
            )

    def get_selected_scan_id(self) -> str | None:
        """Return the scan_id of the current cursor row."""
        if self.cursor_row is None:
            return None
        row = self.get_row_at(self.cursor_row)
        return str(row[1]) if row else None
