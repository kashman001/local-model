"""Browser chat client — FastAPI + Jinja2 + HTMX."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from client.config import ClientSettings


def create_app(*, server_url: str = "http://127.0.0.1:8080") -> FastAPI:
    base = Path(__file__).parent
    templates = Jinja2Templates(directory=str(base / "templates"))

    app = FastAPI(title="local-model client", version="0.1.0")
    app.state.server_url = server_url
    app.state.client = httpx.AsyncClient(base_url=server_url, timeout=120.0)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse(request=request, name="index.html", context={})

    app.mount("/static", StaticFiles(directory=str(base / "static")), name="static")
    return app


def build_app_from_env() -> FastAPI:
    settings = ClientSettings()
    logging.basicConfig(level="INFO")
    primary = settings.endpoints[0]
    return create_app(server_url=primary["url"])
