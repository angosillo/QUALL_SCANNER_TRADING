"""
Result table widget — displays scan results with sorting.
"""

import pandas as pd
from textual.widgets import DataTable


class ResultTable(DataTable):
    """DataTable showing scan results."""

    def __init__(self) -> None:
        super().__init__(id="result_table")
        self.cursor_type = "row"
        self._df: pd.DataFrame = pd.DataFrame()
        self._columns: list[str] = []
        self._sort_col: str | None = None
        self._sort_asc: bool = True

    def load_results(self, df: pd.DataFrame, display_fields: list[str]) -> None:
        """Populate table with scan results."""
        self._df = df.copy()
        self._columns = [f for f in display_fields if f in df.columns]
        if not self._columns:
            self._columns = ["symbol", "close", "volume"]

        self.clear(columns=True)
        self.add_columns(*self._columns)

        for _, row in df.iterrows():
            values = []
            for col in self._columns:
                val = row.get(col, "")
                if isinstance(val, float):
                    val = f"{val:.2f}"
                values.append(str(val))
            self.add_row(*values, key=str(row.get("symbol", "")))

    def toggle_sort(self) -> None:
        """Cycle sort column."""
        if not self._columns:
            return
        if self._sort_col is None:
            self._sort_col = self._columns[0]
            self._sort_asc = True
        else:
            idx = self._columns.index(self._sort_col)
            if idx + 1 < len(self._columns):
                self._sort_col = self._columns[idx + 1]
            else:
                self._sort_col = self._columns[0]
                self._sort_asc = not self._sort_asc

        if self._sort_col in self._df.columns:
            sorted_df = self._df.sort_values(
                self._sort_col, ascending=self._sort_asc, na_position="last"
            )
            self.load_results(sorted_df, self._columns)

    def get_selected_symbol(self) -> str | None:
        """Return the symbol of the current cursor row."""
        if self.cursor_row is None:
            return None
        row = self.get_row_at(self.cursor_row)
        if not row or not self._columns:
            return None
        # symbol is typically the first column
        return str(row[0]) if row else None

    def filter_by_symbol(self, query: str) -> None:
        """Filter results by symbol substring."""
        if self._df.empty or "symbol" not in self._df.columns:
            return
        filtered = self._df[self._df["symbol"].str.contains(query, case=False, na=False)]
        self.load_results(filtered, self._columns)
