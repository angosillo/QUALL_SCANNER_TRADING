"""
Watchlist screen — CRUD and viewing of watchlists.
"""

import logging

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from ...watchlist.manager import (
    auto_populate,
    create_watchlist,
    delete_watchlist,
    get_items,
    list_watchlists,
    remove_symbol,
    rename_watchlist,
)

logger = logging.getLogger(__name__)


class CreateWatchlistModal(ModalScreen[str | None]):
    """Modal to create a new watchlist."""

    def compose(self):
        yield Vertical(
            Label("Nueva Watchlist", classes="header"),
            Input(placeholder="Nombre", id="name_input"),
            Input(placeholder="Descripción (opcional)", id="desc_input"),
            Horizontal(
                Button("Crear", variant="success", id="create_btn"),
                Button("Cancelar", variant="error", id="cancel_btn"),
            ),
            classes="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create_btn":
            name = self.query_one("#name_input", Input).value.strip()
            desc = self.query_one("#desc_input", Input).value.strip()
            if name:
                self.dismiss(f"{name}|{desc}")
            else:
                self.notify("El nombre es obligatorio", severity="error")
        else:
            self.dismiss(None)


class RenameWatchlistModal(ModalScreen[str | None]):
    """Modal to rename a watchlist."""

    def __init__(self, current_name: str) -> None:
        super().__init__()
        self.current_name = current_name

    def compose(self):
        yield Vertical(
            Label("Renombrar Watchlist", classes="header"),
            Input(value=self.current_name, id="name_input"),
            Horizontal(
                Button("Guardar", variant="success", id="save_btn"),
                Button("Cancelar", variant="error", id="cancel_btn"),
            ),
            classes="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save_btn":
            name = self.query_one("#name_input", Input).value.strip()
            if name:
                self.dismiss(name)
            else:
                self.notify("El nombre es obligatorio", severity="error")
        else:
            self.dismiss(None)


class ConfirmDeleteModal(ModalScreen[bool]):
    """Modal to confirm deletion."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name

    def compose(self):
        yield Vertical(
            Label(f"¿Eliminar '{self.name}'?", classes="header"),
            Horizontal(
                Button("Sí", variant="error", id="yes_btn"),
                Button("No", variant="primary", id="no_btn"),
            ),
            classes="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes_btn")


class WatchlistItemsScreen(Screen):
    """Screen showing items inside a watchlist."""

    BINDINGS = [
        Binding("a", "auto_populate", "Auto-populate"),
        Binding("r", "remove_symbol", "Remove"),
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, db_path: str, watchlist_id: int, watchlist_name: str) -> None:
        super().__init__()
        self.db_path = db_path
        self.watchlist_id = watchlist_id
        self.watchlist_name = watchlist_name
        self._status = Static(f"{watchlist_name}", id="status")
        self._table = DataTable(id="items_table")
        self._table.cursor_type = "row"

    def compose(self):
        yield Header()
        yield self._status
        yield self._table
        yield Footer()

    def on_mount(self) -> None:
        self._load_items()

    def _load_items(self) -> None:
        try:
            df = get_items(self.db_path, self.watchlist_id)
            self._table.clear(columns=True)
            cols = ["symbol", "added_at", "flagged", "close", "volume", "adr_pct_20", "trend_intensity", "composite_score"]
            available = [c for c in cols if c in df.columns]
            self._table.add_columns(*available)
            for _, row in df.iterrows():
                values = []
                for c in available:
                    val = row.get(c, "")
                    if c == "flagged":
                        val = "⚑" if val else ""
                    elif isinstance(val, float):
                        val = f"{val:.2f}"
                    values.append(str(val))
                self._table.add_row(*values, key=str(row.get("symbol", "")))
            self._status.update(f"{self.watchlist_name} — {len(df)} símbolos")
        except Exception as exc:
            logger.error(f"Error loading watchlist items: {exc}")
            self._status.update(f"Error: {exc}")

    def action_auto_populate(self) -> None:
        try:
            count = auto_populate(self.db_path, self.watchlist_id)
            self.notify(f"Auto-populado: {count} símbolos añadidos")
            self._load_items()
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error")

    def action_remove_symbol(self) -> None:
        if self._table.cursor_row is None:
            self.notify("Selecciona un símbolo", severity="warning")
            return
        row = self._table.get_row_at(self._table.cursor_row)
        symbol = str(row[0]) if row else None
        if symbol:
            try:
                remove_symbol(self.db_path, self.watchlist_id, symbol)
                self.notify(f"{symbol} eliminado")
                self._load_items()
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error")

    def action_go_back(self) -> None:
        self.app.pop_screen()


class WatchlistScreen(Screen):
    """Screen listing all watchlists."""

    BINDINGS = [
        Binding("n", "new_watchlist", "New"),
        Binding("d", "delete_watchlist", "Delete"),
        Binding("r", "rename_watchlist", "Rename"),
        Binding("enter", "open_watchlist", "Open"),
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, db_path: str) -> None:
        super().__init__()
        self.db_path = db_path
        self._table = DataTable(id="watchlist_table")
        self._table.cursor_type = "row"
        self._table.add_columns("ID", "Nombre", "Descripción", "Auto-populate", "Items")
        self._status = Static("Cargando watchlists...", id="status")

    def compose(self):
        yield Header()
        yield self._status
        yield self._table
        yield Footer()

    def on_mount(self) -> None:
        self._load_watchlists()

    def _load_watchlists(self) -> None:
        try:
            df = list_watchlists(self.db_path)
            self._table.clear()
            for _, row in df.iterrows():
                self._table.add_row(
                    str(row["id"]),
                    str(row["name"]),
                    str(row.get("description", "")),
                    str(row.get("auto_populate_scan", "") or ""),
                    str(row.get("item_count", 0)),
                    key=str(row["id"]),
                )
            self._status.update(f"Watchlists: {len(df)}")
        except Exception as exc:
            logger.error(f"Error loading watchlists: {exc}")
            self._status.update(f"Error: {exc}")

    def _get_selected_id(self) -> int | None:
        if self._table.cursor_row is None:
            return None
        row = self._table.get_row_at(self._table.cursor_row)
        if row:
            try:
                return int(row[0])
            except (ValueError, IndexError):
                pass
        return None

    def action_new_watchlist(self) -> None:
        def handle_result(result: str | None) -> None:
            if result is None:
                return
            parts = result.split("|", 1)
            name = parts[0]
            desc = parts[1] if len(parts) > 1 else ""
            try:
                create_watchlist(self.db_path, name, desc)
                self.notify(f"Watchlist '{name}' creada")
                self._load_watchlists()
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error")

        self.app.push_screen(CreateWatchlistModal(), handle_result)

    def action_delete_watchlist(self) -> None:
        wl_id = self._get_selected_id()
        if wl_id is None:
            self.notify("Selecciona una watchlist", severity="warning")
            return
        row = self._table.get_row_at(self._table.cursor_row)
        name = str(row[1]) if row else str(wl_id)

        def handle_result(confirmed: bool) -> None:
            if confirmed:
                try:
                    delete_watchlist(self.db_path, wl_id)
                    self.notify(f"Watchlist '{name}' eliminada")
                    self._load_watchlists()
                except Exception as exc:
                    self.notify(f"Error: {exc}", severity="error")

        self.app.push_screen(ConfirmDeleteModal(name), handle_result)

    def action_rename_watchlist(self) -> None:
        wl_id = self._get_selected_id()
        if wl_id is None:
            self.notify("Selecciona una watchlist", severity="warning")
            return
        row = self._table.get_row_at(self._table.cursor_row)
        current_name = str(row[1]) if row else ""

        def handle_result(new_name: str | None) -> None:
            if new_name:
                try:
                    rename_watchlist(self.db_path, wl_id, new_name)
                    self.notify(f"Renombrado a '{new_name}'")
                    self._load_watchlists()
                except Exception as exc:
                    self.notify(f"Error: {exc}", severity="error")

        self.app.push_screen(RenameWatchlistModal(current_name), handle_result)

    def action_open_watchlist(self) -> None:
        wl_id = self._get_selected_id()
        if wl_id is None:
            self.notify("Selecciona una watchlist", severity="warning")
            return
        row = self._table.get_row_at(self._table.cursor_row)
        name = str(row[1]) if row else str(wl_id)
        self.app.push_screen(WatchlistItemsScreen(self.db_path, wl_id, name))

    def action_go_back(self) -> None:
        self.app.pop_screen()
