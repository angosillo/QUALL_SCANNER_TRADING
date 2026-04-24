"""
FastAPI application factory for MOMO Scanner web dashboard.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .dependencies import get_db_path, load_web_config
from .routes import dashboard, scan, symbol, watchlist

logger = logging.getLogger(__name__)


def _template_dir() -> str:
    return str(Path(__file__).parent / "templates")


def _static_dir() -> str:
    return str(Path(__file__).parent / "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("MOMO web dashboard starting")
    yield
    logger.info("MOMO web dashboard shutting down")


def create_app(db_path: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    web_cfg = load_web_config()
    db_path = db_path or get_db_path()

    app = FastAPI(
        title=web_cfg["title"],
        lifespan=lifespan,
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=_static_dir()), name="static")

    # Templates
    templates = Jinja2Templates(directory=_template_dir())

    # Store shared state
    app.state.db_path = db_path
    app.state.web_cfg = web_cfg
    app.state.templates = templates

    # Include routers
    app.include_router(dashboard.router)
    app.include_router(scan.router)
    app.include_router(symbol.router)
    app.include_router(watchlist.router)

    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request):
        return RedirectResponse(url="/dashboard", status_code=302)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception")
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": str(exc)},
            status_code=500,
        )

    return app
