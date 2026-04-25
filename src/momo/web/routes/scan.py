"""Scan routes — results table and CSV export."""

import logging
from datetime import datetime
from io import StringIO

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from ...scanner.engine import build_indicator_table, run_scan
from ...scanner.loader import load_all_scans
from ...watchlist.manager import list_watchlists

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/scan/{scan_id}", response_class=HTMLResponse)
async def scan_detail(request: Request, scan_id: str):
    db_path = request.app.state.db_path
    web_cfg = request.app.state.web_cfg
    templates = request.app.state.templates

    scans = load_all_scans("config/scans")
    scan_config = next((s for s in scans if s["scan"]["id"] == scan_id), None)
    if scan_config is None:
        return templates.TemplateResponse(
            request,
            "error.html", {"message": f"Scan '{scan_id}' no encontrado"}, status_code=404
        )

    # Load results from DB history
    import sqlite3
    df = pd.DataFrame()
    try:
        conn = sqlite3.connect(db_path)
        query = """
            SELECT * FROM scan_results
            WHERE scan_id = ? AND run_date = (
                SELECT MAX(run_date) FROM scan_results WHERE scan_id = ?
            )
            ORDER BY rank_in_scan
        """
        df = pd.read_sql(query, conn, params=(scan_id, scan_id))
        conn.close()
    except Exception as exc:
        logger.warning(f"Could not load from DB: {exc}")

    if df.empty:
        try:
            indicator_table = build_indicator_table(db_path)
            if not indicator_table.empty:
                df = run_scan(scan_config, indicator_table, db_path)
        except Exception as exc:
            logger.error(f"Scan execution failed: {exc}")

    display_cfg = scan_config.get("display", {})
    fields = display_cfg.get("fields", ["symbol", "close", "volume"])
    watchlists = list_watchlists(db_path)

    return templates.TemplateResponse(
        request,
        "scan_detail.html",
        {
            "title": scan_config["scan"]["name"],
            "scan": scan_config,
            "results": df,
            "fields": fields,
            "watchlists": watchlists,
        },
    )


@router.get("/scan/{scan_id}/charts", response_class=HTMLResponse)
async def scan_charts(request: Request, scan_id: str):
    db_path = request.app.state.db_path
    web_cfg = request.app.state.web_cfg
    templates = request.app.state.templates

    scans = load_all_scans("config/scans")
    scan_config = next((s for s in scans if s["scan"]["id"] == scan_id), None)
    if scan_config is None:
        return templates.TemplateResponse(
            request,
            "error.html", {"message": f"Scan '{scan_id}' no encontrado"}, status_code=404
        )

    import sqlite3
    df = pd.DataFrame()
    try:
        conn = sqlite3.connect(db_path)
        query = """
            SELECT sr.*, t.exchange 
            FROM scan_results sr
            LEFT JOIN tickers t ON sr.symbol = t.symbol
            WHERE sr.scan_id = ? AND sr.run_date = (
                SELECT MAX(run_date) FROM scan_results WHERE sr.scan_id = ?
            )
            ORDER BY sr.rank_in_scan
        """
        df = pd.read_sql(query, conn, params=(scan_id, scan_id))
        conn.close()
    except Exception as exc:
        logger.warning(f"Could not load from DB: {exc}")

    if df.empty:
        try:
            indicator_table = build_indicator_table(db_path)
            if not indicator_table.empty:
                df = run_scan(scan_config, indicator_table, db_path)
        except Exception as exc:
            logger.error(f"Scan execution failed: {exc}")

    symbols = df["symbol"].tolist() if not df.empty else []

    # Fetch fundamentals for quality badge display
    symbol_meta: dict = {}
    if symbols:
        try:
            import sqlite3 as _sq3
            conn_meta = _sq3.connect(db_path)
            placeholders = ",".join("?" * len(symbols))

            # market_cap, float_shares, sector from tickers
            ticker_rows = conn_meta.execute(
                f"SELECT symbol, market_cap, float_shares, sector FROM tickers WHERE symbol IN ({placeholders})",
                symbols,
            ).fetchall()
            for sym, mc, fl, sec in ticker_rows:
                symbol_meta[sym] = {
                    "market_cap": mc,
                    "float_shares": fl,
                    "sector": sec or "",
                    "rvol": None,
                    "float_rotation": None,
                }

            # latest volume + 20-day avg per symbol
            vol_rows = conn_meta.execute(
                f"""
                SELECT dp.symbol, dp.volume, avg_sub.avg_vol
                FROM daily_prices dp
                JOIN (
                    SELECT symbol, AVG(volume) AS avg_vol
                    FROM (
                        SELECT symbol, volume FROM daily_prices
                        WHERE symbol IN ({placeholders})
                        ORDER BY date DESC LIMIT 999999
                    )
                    GROUP BY symbol
                ) avg_sub ON dp.symbol = avg_sub.symbol
                WHERE dp.symbol IN ({placeholders})
                AND dp.date = (SELECT MAX(date) FROM daily_prices WHERE symbol = dp.symbol)
                """,
                symbols + symbols + symbols,
            ).fetchall()

            for sym, vol, avg_vol in vol_rows:
                meta = symbol_meta.setdefault(sym, {"market_cap": None, "float_shares": None, "sector": "", "rvol": None, "float_rotation": None})
                if avg_vol and avg_vol > 0:
                    meta["rvol"] = round(vol / avg_vol, 1)
                fl = meta.get("float_shares")
                if fl and fl > 0 and vol:
                    meta["float_rotation"] = round(vol / fl, 2)

            conn_meta.close()
        except Exception as exc:
            logger.warning(f"Could not fetch fundamentals for badges: {exc}")

    # Pick 3 key fields for the summary table
    table_fields = ["symbol", "close", "volume"]
    available = [c for c in df.columns if c in table_fields]
    if len(available) < 3:
        available = list(df.columns)[:3] if not df.empty else ["symbol"]

    return templates.TemplateResponse(
        request,
        "scan_charts.html",
        {
            "title": f"{scan_config['scan']['name']} — Charts",
            "scan": scan_config,
            "symbols": symbols,
            "symbol_meta": symbol_meta,
            "results": df,
            "table_fields": available,
        },
    )


@router.get("/scan/{scan_id}.csv")
async def scan_export_csv(request: Request, scan_id: str):
    db_path = request.app.state.db_path
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        query = """
            SELECT * FROM scan_results
            WHERE scan_id = ? AND run_date = (
                SELECT MAX(run_date) FROM scan_results WHERE scan_id = ?
            )
            ORDER BY rank_in_scan
        """
        df = pd.read_sql(query, conn, params=(scan_id, scan_id))
        conn.close()
    except Exception as exc:
        logger.error(f"CSV export failed: {exc}")
        return PlainTextResponse("Error exportando CSV", status_code=500)

    if df.empty:
        return PlainTextResponse("No hay resultados", status_code=404)

    date_str = datetime.now().strftime("%Y%m%d")
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    return PlainTextResponse(
        csv_buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{date_str}_{scan_id}.csv"'},
    )
