"""Watchlist routes — CRUD and detail views."""

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...watchlist.manager import (
    add_symbol,
    auto_populate,
    create_watchlist,
    delete_watchlist,
    get_items,
    list_watchlists,
    remove_symbol,
    rename_watchlist,
)
from ...scanner.loader import load_all_scans

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/watchlists", response_class=HTMLResponse)
async def watchlists_list(request: Request):
    db_path = request.app.state.db_path
    templates = request.app.state.templates

    wls = list_watchlists(db_path)
    scans = load_all_scans("config/scans")
    scan_ids = [s["scan"]["id"] for s in scans]

    return templates.TemplateResponse(
        request,
        "watchlists.html",
        {
            "title": "Watchlists",
            "watchlists": wls,
            "scan_ids": scan_ids,
        },
    )


@router.post("/watchlists")
async def watchlists_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    auto_populate_scan: str = Form(""),
):
    db_path = request.app.state.db_path
    try:
        create_watchlist(
            db_path,
            name=name,
            description=description,
            auto_populate_scan=auto_populate_scan or None,
        )
    except Exception as exc:
        logger.error(f"Create watchlist failed: {exc}")
    return RedirectResponse(url="/watchlists", status_code=303)


@router.get("/watchlists/{watchlist_id}", response_class=HTMLResponse)
async def watchlist_detail(request: Request, watchlist_id: int):
    db_path = request.app.state.db_path
    templates = request.app.state.templates

    wls = list_watchlists(db_path)
    wl = wls[wls["id"] == watchlist_id]
    if wl.empty:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": f"Watchlist {watchlist_id} no encontrada"},
            status_code=404,
        )

    items = get_items(db_path, watchlist_id)
    return templates.TemplateResponse(
        request,
        "watchlist_detail.html",
        {
            "title": wl.iloc[0]["name"],
            "watchlist": wl.iloc[0],
            "items": items,
        },
    )


@router.post("/watchlists/{watchlist_id}/rename")
async def watchlist_rename(
    request: Request,
    watchlist_id: int,
    name: str = Form(...),
):
    db_path = request.app.state.db_path
    try:
        rename_watchlist(db_path, watchlist_id, name)
    except Exception as exc:
        logger.error(f"Rename watchlist failed: {exc}")
    return RedirectResponse(url="/watchlists", status_code=303)


@router.post("/watchlists/{watchlist_id}/delete")
async def watchlist_delete(request: Request, watchlist_id: int):
    db_path = request.app.state.db_path
    try:
        delete_watchlist(db_path, watchlist_id)
    except Exception as exc:
        logger.error(f"Delete watchlist failed: {exc}")
    return RedirectResponse(url="/watchlists", status_code=303)


@router.post("/watchlists/{watchlist_id}/add")
async def watchlist_add_symbol(
    request: Request,
    watchlist_id: int,
    symbol: str = Form(...),
    added_from_scan: str = Form(""),
    notes: str = Form(""),
):
    db_path = request.app.state.db_path
    try:
        add_symbol(
            db_path,
            watchlist_id,
            symbol.upper(),
            added_from_scan=added_from_scan or None,
            notes=notes,
        )
    except Exception as exc:
        logger.error(f"Add symbol failed: {exc}")
    referer = request.headers.get("referer", "/watchlists")
    return RedirectResponse(url=referer, status_code=303)


@router.post("/watchlists/{watchlist_id}/remove/{symbol}")
async def watchlist_remove_symbol(request: Request, watchlist_id: int, symbol: str):
    db_path = request.app.state.db_path
    try:
        remove_symbol(db_path, watchlist_id, symbol.upper())
    except Exception as exc:
        logger.error(f"Remove symbol failed: {exc}")
    return RedirectResponse(url=f"/watchlists/{watchlist_id}", status_code=303)


@router.post("/watchlists/{watchlist_id}/auto_populate")
async def watchlist_auto_populate(request: Request, watchlist_id: int):
    db_path = request.app.state.db_path
    try:
        count = auto_populate(db_path, watchlist_id)
        logger.info(f"Auto-populated watchlist {watchlist_id} with {count} symbols")
    except Exception as exc:
        logger.error(f"Auto-populate failed: {exc}")
    return RedirectResponse(url=f"/watchlists/{watchlist_id}", status_code=303)
