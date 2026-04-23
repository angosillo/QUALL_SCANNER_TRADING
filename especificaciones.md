# Especificaciones — MOMO Scanner UI

**Audiencia**: Hermes (agente IA implementador)
**Fecha**: 2026-04-23
**Objetivo**: Construir la interfaz TUI del escáner y las features pendientes (`ui/`, `charts/`, `watchlist/`).

---

## 1. Contexto del proyecto

MOMO Scanner es un escáner de momentum bursátil inspirado en la metodología de Qullamaggie. El pipeline de datos, indicadores, filtros y scoring **ya está implementado y funcional**. Lo que falta es la capa de visualización y gestión de watchlists.

**Stack existente (NO introducir dependencias nuevas salvo que sea indispensable):**

- Python >= 3.12
- `pandas`, `numpy`, `pandas-ta` — datos e indicadores
- `textual >= 0.80` — ya en dependencias, **usar esto para la TUI**
- `rich >= 13.7` — formato de tablas, complementa Textual
- `mplfinance`, `plotly` — gráficos (ya en deps)
- `tomli` — lectura de configs TOML
- `apscheduler` — scheduling
- `python-telegram-bot` — alertas
- `fastapi`, `uvicorn`, `jinja2` — opcionales (web), **no usar para esta fase**
- SQLite como persistencia

---

## 2. Estado actual del código (NO reinventar)

### 2.1 Estructura
```
src/momo/
├── data/            [✅ completo] ingest, providers (FMP, Nasdaq FTP, yfinance)
├── indicators/      [✅ completo] adr_percent, price_rank, trend_intensity
├── scanner/         [✅ completo] engine, filters, loader
├── scoring/         [✅ completo] composite score 0-100
├── alerts/          [✅ completo] telegram_alerts
├── ui/              [🔲 VACÍO — construir aquí la TUI]
├── charts/          [🔲 VACÍO — construir aquí los gráficos]
├── watchlist/       [🔲 VACÍO — construir aquí la gestión de watchlists]
└── main.py          [✅ CLI: init | universe | download | scan | full]
```

### 2.2 Patrones establecidos que DEBEN respetarse

- **CLI con argparse subparsers** (ver `src/momo/main.py`). Toda nueva entrada de CLI se agrega como subparser ahí.
- **Configs en TOML** (`config/settings.toml` y `config/scans/*.toml`).
- **Filtros**: heredan de `Filter` (ABC) y se componen en `FilterChain` (ver `scanner/filters.py`). Cualquier filtro nuevo debe seguir ese patrón.
- **Acceso a datos**: usar siempre las funciones de `momo.data.ingest`:
  - `get_connection(db_path)` — devuelve conexión con WAL habilitado
  - `get_prices(db_path, symbols, days)` — OHLCV en formato largo
  - `get_close_wide(db_path, symbols, days)` — closes en formato wide
  - `get_universe_symbols(db_path, universe)` — lista de tickers
- **Logging**: `logger = logging.getLogger(__name__)` en cada módulo.
- **Resultados de scans**: se persisten en tabla `scan_results` vía `engine.save_scan_results()`.

### 2.3 Esquema SQLite existente (ver `data/ingest.py::DB_SCHEMA`)

Tablas ya creadas y listas para usar:

- `tickers` — universo con clasificación (exchange, country, universe, sector, industry, market_cap, float_shares, ipo_date)
- `daily_prices` — OHLCV + dollar_volume
- `indicators` — snapshot de indicadores por fecha
- `scan_results` — historial de scans con snapshot JSON
- **`watchlists`** — ya existe la tabla, lista para usar
- **`watchlist_items`** — ya existe la tabla con campos `flagged`, `added_from_scan`, `notes`
- `alerts` — para alertas intraday

**IMPORTANTE**: las tablas `watchlists` y `watchlist_items` **ya existen en el esquema**. No crear tablas nuevas, usar estas.

---

## 3. Lo que hay que construir

### 3.1 Módulo `ui/` — TUI principal con Textual

Objetivo: dashboard de terminal para explorar los resultados de los scans en tiempo real.

#### Pantallas requeridas

**Pantalla 1 — Dashboard principal (`DashboardScreen`)**
- Lista de todos los scans configurados (leer desde `config/scans/*.toml` usando `scanner.loader.load_all_scans`)
- Por cada scan mostrar: nombre, ID, side (long/short), frequency, enabled, nº de resultados de la última corrida
- Navegación con flechas + Enter para entrar al detalle del scan
- Atajos de teclado:
  - `r` — re-ejecutar todos los scans habilitados (`scanner.engine.run_all_scans`)
  - `q` — salir
  - `w` — ir a watchlists
  - `?` — ayuda

**Pantalla 2 — Detalle de scan (`ScanResultScreen`)**
- Tabla con los resultados del scan seleccionado
- Columnas a mostrar: las definidas en `[display].fields` del TOML del scan
- Ordenamiento configurable (respetar `display.sort_by` / `sort_order` como default)
- Filtros rápidos en la barra superior (mínimo: filtro por símbolo string-match)
- Atajos:
  - `Enter` — abrir detalle del símbolo
  - `a` — añadir símbolo seleccionado a una watchlist
  - `c` — ver gráfico del símbolo
  - `s` — cambiar ordenamiento
  - `Esc` — volver al dashboard
  - `e` — exportar a CSV (usar patrón existente en `main.py::cmd_scan`)

**Pantalla 3 — Detalle de símbolo (`SymbolDetailScreen`)**
- Panel superior: todos los indicadores del símbolo (close, volume, adr_pct_20, trend_intensity, composite_score y sus componentes `score_*`, price_growth_* y rank_*)
- Panel inferior: gráfico de velas ASCII o Rich plot (ver sección 3.2) con últimas 60 sesiones
- Tabla histórica: últimas 20 sesiones OHLCV
- Atajos:
  - `a` — añadir a watchlist
  - `Esc` — volver

**Pantalla 4 — Watchlists (`WatchlistScreen`)**
- Lista de watchlists del usuario (tabla `watchlists`)
- Por cada watchlist: nº de símbolos, scan de auto-populate si tiene
- Navegación y CRUD: crear, renombrar, eliminar
- Al entrar a una watchlist: tabla de símbolos con sus indicadores actuales
- Atajos:
  - `n` — nueva watchlist
  - `d` — eliminar watchlist seleccionada
  - `Enter` — abrir watchlist

#### Estructura de archivos sugerida
```
src/momo/ui/
├── __init__.py
├── app.py                   # MomoApp(textual.App) — entry point
├── screens/
│   ├── __init__.py
│   ├── dashboard.py         # DashboardScreen
│   ├── scan_result.py       # ScanResultScreen
│   ├── symbol_detail.py     # SymbolDetailScreen
│   └── watchlist.py         # WatchlistScreen
├── widgets/
│   ├── __init__.py
│   ├── scan_table.py        # Tabla de scans (DataTable)
│   ├── result_table.py      # Tabla de resultados con ordenamiento
│   └── indicator_panel.py   # Panel de indicadores del símbolo
└── styles.tcss              # Textual CSS para el look & feel
```

#### Entry point
Agregar un subcomando `tui` al CLI en `main.py`:

```python
def cmd_tui(args):
    """Launch the Textual TUI."""
    from momo.ui.app import MomoApp
    db_path = get_db_path()
    app = MomoApp(db_path=db_path)
    app.run()
```

Y registrarlo en el `subparsers`:
```python
subparsers.add_parser("tui", help="Launch interactive TUI dashboard")
```

Uso: `python -m momo tui`

---

### 3.2 Módulo `charts/` — Gráficos

Objetivo: generar gráficos de velas para inspección visual de símbolos.

#### Funciones requeridas

```python
# src/momo/charts/candlestick.py

def render_ascii_candles(
    df: pd.DataFrame,
    symbol: str,
    days: int = 60,
    width: int = 80,
    height: int = 20,
) -> str:
    """
    Genera un gráfico de velas ASCII para renderizar dentro de Textual.
    Usar `rich.panel.Panel` o `rich.text.Text` para el output.
    """
    ...

def save_mpl_chart(
    df: pd.DataFrame,
    symbol: str,
    output_path: str,
    days: int = 120,
    show_volume: bool = True,
    show_sma: list[int] = [20, 50, 200],
) -> str:
    """
    Genera un PNG con mplfinance. Usar para exportación desde la TUI.
    Retorna la ruta del archivo generado.
    """
    ...

def save_plotly_chart(
    df: pd.DataFrame,
    symbol: str,
    output_path: str,
    days: int = 120,
) -> str:
    """
    Genera un HTML interactivo con Plotly para compartir/ver en browser.
    """
    ...
```

#### Requisitos
- El input `df` debe ser el formato estándar devuelto por `data.ingest.get_prices()` filtrado por símbolo
- Los gráficos deben incluir overlay opcional de SMA(20), SMA(50), SMA(200)
- Panel inferior con volumen
- El ASCII chart es el default en la TUI; mplfinance/plotly se invocan bajo demanda con atajo

---

### 3.3 Módulo `watchlist/` — Gestión de watchlists

Objetivo: CRUD de watchlists persistentes en SQLite (las tablas ya existen).

#### Funciones requeridas

```python
# src/momo/watchlist/manager.py

def create_watchlist(db_path: str, name: str, description: str = "",
                    auto_populate_scan: str | None = None) -> int:
    """Crea una watchlist. Retorna su ID. Lanza ValueError si el nombre ya existe."""

def list_watchlists(db_path: str) -> pd.DataFrame:
    """Lista watchlists con conteo de items."""

def delete_watchlist(db_path: str, watchlist_id: int) -> None:
    """Elimina watchlist y sus items (cascade manual)."""

def rename_watchlist(db_path: str, watchlist_id: int, new_name: str) -> None:
    """Renombra una watchlist."""

def add_symbol(db_path: str, watchlist_id: int, symbol: str,
              added_from_scan: str | None = None, notes: str = "") -> None:
    """Añade un símbolo. Idempotente (no duplica)."""

def remove_symbol(db_path: str, watchlist_id: int, symbol: str) -> None:
    """Remueve un símbolo de la watchlist."""

def get_items(db_path: str, watchlist_id: int) -> pd.DataFrame:
    """
    Retorna los items de la watchlist JOIN con últimos indicadores.
    Columnas: symbol, added_at, added_from_scan, notes, flagged,
              close, volume, adr_pct_20, trend_intensity, composite_score
    """

def toggle_flag(db_path: str, watchlist_id: int, symbol: str) -> bool:
    """Toggle el campo flagged. Retorna el nuevo estado."""

def auto_populate(db_path: str, watchlist_id: int) -> int:
    """
    Si la watchlist tiene auto_populate_scan, añade todos los símbolos
    del último run de ese scan. Retorna el nº añadido.
    """
```

#### Entry points CLI (opcional pero recomendado)

Agregar subcomando `watchlist` en `main.py` con sub-subparsers:
```
python -m momo watchlist list
python -m momo watchlist create <nombre>
python -m momo watchlist add <nombre> <symbol>
python -m momo watchlist show <nombre>
```

---

## 4. Reglas duras (NO negociables)

1. **NO introducir dependencias nuevas** sin justificación explícita. Todo lo necesario ya está en `pyproject.toml`.
2. **NO modificar** el esquema SQLite en `ingest.py::DB_SCHEMA`. Las tablas de watchlists ya están.
3. **NO cambiar** las firmas de funciones públicas en `data/`, `indicators/`, `scanner/`, `scoring/`. Son la base sobre la que se construye.
4. **NO crear nuevos formatos de config** — si hace falta configurar algo nuevo, agregarlo a `config/settings.toml` bajo una sección dedicada.
5. **Respetar el patrón Filter/FilterChain** si se agrega algún filtro nuevo.
6. **Logging** vía `logging.getLogger(__name__)`, no `print` en código de lógica. Los `print` quedan solo en la capa CLI (`main.py`) y en la TUI para mensajes de usuario.
7. **Tipos**: usar type hints en todas las funciones públicas. Python 3.12+ (`str | None`, `list[str]`, etc.).
8. **Idempotencia**: operaciones de escritura en DB (watchlists, scan_results) deben ser seguras ante reejecución.
9. **Errores**: usar excepciones específicas (`ValueError`, etc.), no `Exception` genérica. La TUI debe capturar y mostrar al usuario sin crashear.

---

## 5. Criterios de aceptación

La implementación se considera completa cuando:

- [ ] `python -m momo tui` levanta una TUI funcional con Textual
- [ ] Desde el dashboard se pueden ver los 6 scans configurados y sus resultados
- [ ] Se puede navegar: dashboard → resultado de scan → detalle de símbolo → volver
- [ ] Desde el detalle de símbolo se ve un gráfico de velas ASCII de las últimas 60 sesiones
- [ ] Se pueden crear, listar y eliminar watchlists desde la TUI
- [ ] Se pueden añadir símbolos a watchlists desde la pantalla de resultados con atajo `a`
- [ ] El export a PNG (mplfinance) funciona con atajo desde el detalle de símbolo
- [ ] No se introdujeron dependencias nuevas
- [ ] Todos los módulos nuevos tienen type hints
- [ ] El código pasa `ruff check src/`
- [ ] La TUI funciona con la base de datos vacía (estado inicial) sin crashear

---

## 6. Orden de implementación sugerido

1. **Módulo `watchlist/manager.py`** — es puro CRUD sobre SQLite, sin dependencias de UI. Testeable en aislamiento.
2. **Módulo `charts/candlestick.py`** — empezar por el ASCII (dependencia de la TUI), después mplfinance.
3. **Módulo `ui/`** — construir en este orden:
   a. `app.py` + `DashboardScreen` (lo más simple, lista scans y cuenta resultados)
   b. `ScanResultScreen` (tabla de resultados)
   c. `SymbolDetailScreen` (integra charts y watchlist add)
   d. `WatchlistScreen` (CRUD visual)
4. **CLI entry points** — `tui` subcommand + opcionalmente `watchlist` subcommand.

---

## 7. Referencias rápidas del código existente

| Archivo | Qué provee |
|---|---|
| `src/momo/data/ingest.py` | `init_db`, `get_connection`, `get_prices`, `get_close_wide`, `get_universe_symbols`, schema SQLite completo |
| `src/momo/scanner/engine.py` | `build_indicator_table`, `run_scan`, `run_all_scans`, `save_scan_results`, `format_results_table` |
| `src/momo/scanner/loader.py` | `load_all_scans`, `load_scan_config`, `build_filters` |
| `src/momo/scanner/filters.py` | Clases `Filter`, `FilterChain`, `PriceFilter`, `VolumeFilter`, `ADRFilter`, `TrendIntensityFilter`, `RankFilter`, `UniverseFilter`, `ExtensionFilter`, `DailyChangeFilter` |
| `src/momo/scoring/composite.py` | `calculate_composite_score` |
| `src/momo/alerts/telegram_alerts.py` | Patrón de cómo se consume el resultado de `run_all_scans` |
| `config/scans/*.toml` | 6 scans configurados, ejemplos de `display.fields` y `display.sort_by` |
| `config/settings.toml` | Config general del proyecto (db_path, scheduler, data) |

---

**Fin del documento.**
