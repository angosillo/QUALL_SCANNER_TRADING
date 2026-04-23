"""
MOMO Scanner TUI — main Textual application.
"""

from textual.app import App, ComposeResult
from textual.binding import Binding

from .screens.dashboard import DashboardScreen


class MomoApp(App[None]):
    """Main TUI application for MOMO Scanner."""

    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, db_path: str) -> None:
        super().__init__()
        self.db_path = db_path

    def compose(self) -> ComposeResult:
        yield DashboardScreen(self.db_path)

    def action_help(self) -> None:
        """Show help overlay."""
        self.notify(
            "[b]Atajos globales:[/b]\n"
            "  [b]q[/b] — Salir\n"
            "  [b]?[/b] — Esta ayuda\n\n"
            "[b]Dashboard:[/b]\n"
            "  [b]↑↓[/b] — Navegar scans\n"
            "  [b]Enter[/b] — Ver resultados del scan\n"
            "  [b]r[/b] — Re-ejecutar todos los scans\n"
            "  [b]w[/b] — Ir a watchlists\n\n"
            "[b]Resultados:[/b]\n"
            "  [b]Enter[/b] — Detalle del símbolo\n"
            "  [b]a[/b] — Añadir a watchlist\n"
            "  [b]c[/b] — Ver gráfico\n"
            "  [b]s[/b] — Cambiar ordenamiento\n"
            "  [b]e[/b] — Exportar a CSV\n"
            "  [b]Esc[/b] — Volver\n\n"
            "[b]Watchlists:[/b]\n"
            "  [b]n[/b] — Nueva watchlist\n"
            "  [b]d[/b] — Eliminar watchlist\n"
            "  [b]Enter[/b] — Abrir watchlist",
            title="Ayuda",
            timeout=10,
        )
