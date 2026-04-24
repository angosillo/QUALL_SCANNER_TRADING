"""Dashboard route — lists all scans."""

import logging
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...scanner.engine import build_indicator_table, run_all_scans
from ...scanner.loader import load_all_scans
from ..dependencies import get_db_path, load_web_config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    db_path = request.app.state.db_path
    web_cfg = request.app.state.web_cfg
    templates = request.app.state.templates

    scans = load_all_scans("config/scans")
    result_counts = _get_result_counts(db_path)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": web_cfg["title"],
            "scans": scans,
            "result_counts": result_counts,
        },
    )


@router.post("/scans/run")
async def run_all(request: Request):
    db_path = request.app.state.db_path
    try:
        indicator_table = build_indicator_table(db_path)
        if not indicator_table.empty:
            run_all_scans(db_path, "config/scans", indicator_table)
    except Exception as exc:
        logger.error(f"Run all scans failed: {exc}")
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/scans/run/{scan_id}")
async def run_single(request: Request, scan_id: str):
    db_path = request.app.state.db_path
    try:
        from ...scanner.engine import build_indicator_table, run_scan
        scans = load_all_scans("config/scans")
        cfg = next((s for s in scans if s["scan"]["id"] == scan_id), None)
        if cfg:
            indicator_table = build_indicator_table(db_path)
            if not indicator_table.empty:
                run_scan(cfg, indicator_table, db_path)
    except Exception as exc:
        logger.error(f"Run scan {scan_id} failed: {exc}")
    return RedirectResponse(url=f"/scan/{scan_id}", status_code=303)


def _get_result_counts(db_path: str) -> dict[str, int]:
    import sqlite3
    counts: dict[str, int] = {}
    try:
        conn = sqlite3.connect(db_path)
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
