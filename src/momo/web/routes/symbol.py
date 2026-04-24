"""Symbol route — detail with indicators, Plotly chart, and history."""

import logging

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ...charts.candlestick import build_plotly_figure
from ...data.ingest import get_connection
from ...watchlist.manager import list_watchlists

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/symbol/{symbol}", response_class=HTMLResponse)
async def symbol_detail(request: Request, symbol: str):
    db_path = request.app.state.db_path
    web_cfg = request.app.state.web_cfg
    templates = request.app.state.templates

    conn = get_connection(db_path)
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
            params=(symbol,),
        )

        # Historical prices
        prices_df = pd.read_sql(
            """
            SELECT date, open, high, low, close, volume
            FROM daily_prices
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            conn,
            params=(symbol, web_cfg.get("chart_days", 120)),
        )
        prices_df = prices_df.sort_values("date")

        # Last 20 sessions for table
        history = prices_df.tail(20).sort_values("date", ascending=False)

        # Build Plotly figure dict
        chart_dict = None
        if not prices_df.empty:
            try:
                chart_dict = build_plotly_figure(
                    prices_df,
                    symbol,
                    days=web_cfg.get("chart_days", 120),
                    show_sma=web_cfg.get("chart_smas", [20, 50, 200]),
                    show_volume=True,
                )
            except Exception as exc:
                logger.warning(f"Plotly chart build failed: {exc}")

        watchlists = list_watchlists(db_path)
    except Exception as exc:
        logger.error(f"Error loading symbol detail: {exc}")
        return templates.TemplateResponse(
            request,
            "error.html", {"message": str(exc)}, status_code=500
        )
    finally:
        conn.close()

    return templates.TemplateResponse(
        request,
        "symbol_detail.html",
        {
            "title": symbol,
            "symbol": symbol,
            "indicators": indicators_df,
            "history": history,
            "chart_dict": chart_dict,
            "watchlists": watchlists,
        },
    )
