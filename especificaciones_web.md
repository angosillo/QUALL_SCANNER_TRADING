# Especificaciones — MOMO Scanner Web Dashboard

**Audiencia**: Hermes (agente IA implementador)
**Fecha**: 2026-04-24
**Objetivo**: Construir un dashboard web con FastAPI + Jinja2 + Plotly como capa de presentación del escáner.

---

## 0. Contexto — por qué web y no TUI

La versión TUI (Textual) fue implementada pero **no es viable en el entorno de producción**: Windows Server 2022 (Hetzner VDS) usa `conhost.exe`, que no soporta los escape ANSI complejos de Textual. Ver `ERRORES_TUI_DESKTOP.md` para el histórico.

**Decisión**: migrar la capa de presentación a web (FastAPI + Jinja2 + Plotly). La lógica de negocio se mantiene intacta.

---

## 1. Stack — TODO YA ESTÁ EN `pyproject.toml`

```toml
[project.optional-dependencies]
web = ["fastapi>=0.111", "uvicorn>=0.30", "jinja2>=3.1"]
```

Adicionalmente ya disponibles en deps principales:
- `plotly >= 5.22` — gráficos interactivos de velas
- `pandas`, `numpy` — datos
- `tomli` — configs
- SQLite — persistencia

**NO introducir dependencias nuevas.** Instalación:
```bash
pip install -e ".[web]"
```

---

## 2. Estado actual (NO REINVENTAR)

### 2.1 Módulos que se MANTIENEN intactos (lógica de negocio probada)

| Módulo | Rol | NO TOCAR |
|---|---|---|
| `src/momo/data/` | Ingest, providers, schema SQLite | ✅ |
| `src/momo/indicators/` | ADR%, Trend Intensity, Price Rank | ✅ |
| `src/momo/scanner/` | Engine, filters, loader, FilterChain | ✅ |
| `src/momo/scoring/` | Composite score 0-100 | ✅ |
| `src/momo/watchlist/manager.py` | CRUD SQLite de watchlists | ✅ |
| `src/momo/alerts/` | Telegram | ✅ |
| `src/momo/charts/candlestick.py` | **Usar `save_plotly_chart` y añadir `build_plotly_figure`** | Leer sección 3.3 |
| `config/scans/*.toml` | 6 scans configurados | ✅ |
| `config/settings.toml` | Config general | ✅ (extender, ver 5) |

### 2.2 Módulos DEPRECADOS (no tocar, no borrar — referencia de UX)

- `src/momo/ui/` (app.py, screens/, widgets/, styles.tcss)
- `launch-tui.sh`

Quedan en el repo como referencia visual de qué pantallas construir. **No los modifiques ni los borres.** El subcomando `python -m momo tui` también se mantiene funcional por retrocompatibilidad.

### 2.3 Esquema SQLite

Todas las tablas necesarias ya existen (ver `src/momo/data/ingest.py::DB_SCHEMA`):
- `tickers`, `daily_prices`, `indicators`
- `watchlists`, `watchlist_items`
- `scan_results`, `alerts`

**NO modificar el schema.**

---

## 3. Lo que hay que construir

### 3.1 Estructura del módulo `web/`

```
src/momo/web/
├── __init__.py
├── app.py                     # FastAPI application factory + lifespan
├── routes/
│   ├── __init__.py
│   ├── dashboard.py           # GET /  (lista de scans)
│   ├── scan.py                # GET /scan/{scan_id}
│   ├── symbol.py              # GET /symbol/{symbol}
│   └── watchlist.py           # GET/POST /watchlists, /watchlists/{id}
├── templates/
│   ├── base.html              # Layout común
│   ├── dashboard.html         # Lista de scans
│   ├── scan_detail.html       # Tabla de resultados
│   ├── symbol_detail.html     # Indicadores + Plotly chart + historial
│   ├── watchlists.html        # Lista de watchlists
│   └── watchlist_detail.html  # Items de una watchlist
├── static/
│   ├── styles.css             # Dark theme, financial look
│   └── app.js                 # Interacciones mínimas (sort, filter cliente)
└── dependencies.py            # get_db_path() compartido
```

### 3.2 Endpoints

Todos retornan HTML renderizado (Jinja2). Sin SPA, sin API REST. **Server-side rendering puro.**

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Dashboard — lista de 6 scans con conteo de resultados |
| `POST` | `/scans/run` | Re-ejecuta todos los scans, redirige a `/` |
| `POST` | `/scans/run/{scan_id}` | Re-ejecuta un scan, redirige a `/scan/{scan_id}` |
| `GET` | `/scan/{scan_id}` | Tabla de resultados del último run |
| `GET` | `/scan/{scan_id}.csv` | Export CSV (reusar patrón de `main.py::cmd_scan`) |
| `GET` | `/symbol/{symbol}` | Panel de indicadores + gráfico Plotly + historial 20 sesiones |
| `GET` | `/watchlists` | Lista de watchlists (con conteos) |
| `POST` | `/watchlists` | Crear watchlist (form: `name`, `description`, `auto_populate_scan`) |
| `GET` | `/watchlists/{id}` | Detalle de una watchlist (items con últimos indicadores) |
| `POST` | `/watchlists/{id}/rename` | Renombrar (form: `name`) |
| `POST` | `/watchlists/{id}/delete` | Eliminar, redirige a `/watchlists` |
| `POST` | `/watchlists/{id}/add` | Añadir símbolo (form: `symbol`, `added_from_scan?`, `notes?`) |
| `POST` | `/watchlists/{id}/remove/{symbol}` | Remover símbolo |
| `POST` | `/watchlists/{id}/auto_populate` | Llena desde último run del scan asociado |

**Importante**: las acciones destructivas/mutadoras van por `POST`. Usar formularios HTML estándar, no JS fetch. Tras POST siempre hacer `RedirectResponse(status_code=303)` al GET correspondiente.

### 3.3 Extensión de `charts/candlestick.py`

Añadir una función nueva (no tocar las existentes):

```python
def build_plotly_figure(
    df: pd.DataFrame,
    symbol: str,
    days: int = 120,
    show_sma: list[int] | None = None,
    show_volume: bool = True,
) -> dict:
    """
    Retorna el dict JSON de una figura Plotly para embeber en HTML
    via <div id="chart"></div> + Plotly.newPlot().

    Args:
        df: DataFrame con columnas date, open, high, low, close, volume
        symbol: ticker a graficar
        days: número de sesiones a mostrar
        show_sma: periodos de SMA a overlayear (ej [20, 50])
        show_volume: si incluir panel de volumen

    Returns:
        dict con keys "data" y "layout" (formato Plotly JSON)
    """
```

Usar `plotly.graph_objects.Figure.to_dict()` al final. Esto permite pasar el dict a la template y renderizarlo client-side sin generar un HTML standalone.

### 3.4 Pantallas (contenido mínimo de cada template)

**`dashboard.html`** — Tabla de scans:
- Columnas: ID, Nombre, Side (long/short), Habilitado, Último run, N° resultados
- Botón global: "Re-ejecutar todos los scans" (POST /scans/run)
- Click en cada fila → `/scan/{scan_id}`
- Link en el header a `/watchlists`

**`scan_detail.html`** — Resultados del scan:
- Título con nombre del scan + fecha del último run
- Tabla con las columnas de `[display].fields` del TOML
- Cada fila clickeable → `/symbol/{symbol}`
- Campo de input (client-side JS) para filtrar por símbolo
- Botones: "Re-ejecutar scan" (POST), "Export CSV" (GET /scan/{id}.csv)
- Formulario inline por fila: "Añadir a watchlist" con `<select>` de watchlists existentes

**`symbol_detail.html`** — Detalle del símbolo:
- Panel izquierdo: indicadores (close, volume, adr_pct_20, trend_intensity, composite_score + score_* de componentes, growth_* y rank_*)
- Panel central: gráfico Plotly interactivo (usar `build_plotly_figure` + `Plotly.newPlot()`)
- Panel inferior: tabla de las últimas 20 sesiones OHLCV
- Formulario: "Añadir a watchlist" con `<select>`

**`watchlists.html`** — CRUD de watchlists:
- Tabla con: Nombre, Descripción, Auto-populate, Nº items, fechas
- Formulario arriba: crear nueva (inputs para name, description, auto_populate_scan como `<select>` con los 6 scan IDs)
- Por cada watchlist: botones de renombrar (form inline), eliminar (form con confirm JS)

**`watchlist_detail.html`** — Items de una watchlist:
- Tabla con: symbol, added_at, flagged, close, volume, adr_pct_20, trend_intensity, composite_score
- Cada símbolo clickeable → `/symbol/{symbol}`
- Botón por fila: "Remover" (POST)
- Botón global: "Auto-populate desde scan" (si tiene auto_populate_scan)

### 3.5 Template `base.html`

Layout común:
- Navbar superior con links: Dashboard | Watchlists
- Dark theme por defecto
- Footer con versión del proyecto
- Incluir Plotly via CDN:
  ```html
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  ```
  (única dependencia externa permitida, no agregar más CDNs)

---

## 4. Entry point

Agregar subcomando `web` en `src/momo/main.py`:

```python
def cmd_web(args):
    """Launch the web dashboard."""
    import uvicorn
    from momo.web.app import create_app
    db_path = get_db_path()
    app = create_app(db_path=db_path)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
    )

# En el subparser:
p_web = subparsers.add_parser("web", help="Launch web dashboard")
p_web.add_argument("--host", default="0.0.0.0")
p_web.add_argument("--port", type=int, default=8000)
```

Uso:
```bash
python -m momo web --host 0.0.0.0 --port 8000
```

Y luego abrir `http://<server-ip>:8000` en Chrome.

**NO eliminar el subcomando `tui`** — queda para cuando alguien esté en una máquina con terminal moderno.

---

## 5. Configuración

Extender `config/settings.toml` con una sección nueva:

```toml
[web]
host = "0.0.0.0"
port = 8000
title = "MOMO Scanner"
theme = "dark"                 # dark | light
results_page_size = 50         # Filas por página en tablas
chart_days = 120               # Días por defecto en gráficos
chart_smas = [20, 50, 200]     # SMAs a overlay
```

La app web debe leer esta sección al arrancar. CLI flags (`--host`, `--port`) sobrescriben el TOML.

---

## 6. Reglas duras (NO negociables)

1. **NO introducir dependencias nuevas** más allá de `fastapi`, `uvicorn`, `jinja2` (ya en `[web]`) y Plotly via CDN.
2. **NO modificar el schema SQLite** en `data/ingest.py::DB_SCHEMA`.
3. **NO cambiar firmas públicas** de `data/`, `indicators/`, `scanner/`, `scoring/`, `watchlist/manager.py`.
4. **NO modificar ni borrar `ui/`** — queda como legacy funcional.
5. **NO usar SPA frameworks** (React, Vue, etc.). Solo HTML + Jinja + JS vanilla mínimo.
6. **NO usar ORM** (SQLAlchemy, etc.). Seguir el patrón existente: SQL crudo + `pd.read_sql` + `conn.execute`.
7. **NO autenticación ni usuarios**. Es una app local para un operador. Escuchar en `0.0.0.0` asume red confiable (VPN/firewall lo protege).
8. **Server-side rendering** — Jinja renderiza HTML, POST/redirect/GET, nada de fetch+JSON salvo para el gráfico Plotly.
9. **POST siempre redirige** con 303 al GET correspondiente tras la acción.
10. **Logging** vía `logging.getLogger(__name__)`. FastAPI usa su propio logger pero el código de negocio usa el estándar.
11. **Type hints** en todas las funciones públicas. Python 3.12+.
12. **Errores**: capturar en las rutas, mostrar mensaje al usuario vía template `error.html` simple (no stacktraces en producción).

---

## 7. Criterios de aceptación

- [ ] `pip install -e ".[web]"` instala sin fallar
- [ ] `python -m momo web` levanta el servidor en `0.0.0.0:8000`
- [ ] `http://localhost:8000/` muestra el dashboard con los 6 scans
- [ ] Click en un scan lleva a la tabla de resultados
- [ ] Click en un símbolo muestra indicadores + gráfico Plotly interactivo + historial
- [ ] El gráfico Plotly funciona (zoom, hover, pan)
- [ ] Se puede crear, renombrar y eliminar una watchlist
- [ ] Se puede añadir y remover símbolos de una watchlist
- [ ] "Auto-populate" llena una watchlist desde el último run del scan asociado
- [ ] El botón "Re-ejecutar scan" actualiza los resultados
- [ ] Export CSV funciona
- [ ] La app no crashea con DB vacía (estado inicial)
- [ ] `ui/` no fue modificado (verificar con `git diff src/momo/ui/`)
- [ ] No se introdujeron dependencias nuevas
- [ ] `ruff check src/momo/web/` pasa sin errores

---

## 8. Orden de implementación sugerido

1. **`web/app.py` + `create_app()` + `base.html`** — esqueleto mínimo que levanta y muestra "Hello"
2. **`dashboard.html` + ruta `/`** — reutilizar `scanner.loader.load_all_scans` y consulta a `scan_results`
3. **`scan_detail.html` + ruta `/scan/{id}`** — query a `scan_results` con fallback a `run_scan` si no hay historial
4. **Extender `charts/candlestick.py` con `build_plotly_figure`**
5. **`symbol_detail.html` + ruta `/symbol/{symbol}`** — indicadores + Plotly + tabla histórica
6. **`watchlists.html` + `watchlist_detail.html` + rutas** — CRUD completo usando `watchlist.manager`
7. **Export CSV + "Run all scans"** — últimos detalles
8. **`styles.css`** — pulido visual

---

## 9. Referencias rápidas del código existente

| Qué necesitás | Dónde está |
|---|---|
| Cargar configs de scans | `scanner.loader.load_all_scans("config/scans")` |
| Ejecutar un scan | `scanner.engine.run_scan(config, indicator_table, db_path)` |
| Ejecutar todos los scans | `scanner.engine.run_all_scans(db_path, "config/scans")` |
| Construir tabla de indicadores | `scanner.engine.build_indicator_table(db_path)` |
| Conexión SQLite con WAL | `data.ingest.get_connection(db_path)` |
| OHLCV de un símbolo | `data.ingest.get_prices(db_path, symbols=[sym], days=120)` |
| CRUD watchlists | `watchlist.manager.*` (ya tiene `create_watchlist`, `list_watchlists`, `add_symbol`, etc.) |
| Gráfico Plotly PNG/HTML | `charts.candlestick.save_plotly_chart` (existe, añadir `build_plotly_figure`) |
| Config global | `config/settings.toml` leído con `tomli` |
| Scan configs TOML | `config/scans/*.toml` con `[display].fields`, `[scoring]`, etc. |

---

**Fin del documento.**
