"""Browser chat client — FastAPI + Jinja2 + HTMX."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from client.config import ClientSettings

logger = logging.getLogger(__name__)


def create_app(*, server_url: str = "http://127.0.0.1:8080") -> FastAPI:
    base = Path(__file__).parent
    templates = Jinja2Templates(directory=str(base / "templates"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(base_url=server_url, timeout=120.0) as c:
            app.state.client = c
            yield

    app = FastAPI(title="local-model client", version="0.1.0", lifespan=lifespan)
    app.state.server_url = server_url

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, conversation_id: str | None = None):
        messages: list[dict] = []
        if conversation_id:
            try:
                r = await app.state.client.get(f"/history/conversations/{conversation_id}/messages")
                if r.status_code == 200:
                    messages = r.json()
            except Exception as e:
                logger.warning("Failed to load conversation %s: %s", conversation_id, e)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"messages": messages, "conversation_id": conversation_id or ""},
        )

    @app.get("/history", response_class=HTMLResponse)
    async def history_page(request: Request):
        try:
            r = await app.state.client.get("/history/conversations")
            convs = r.json()
        except Exception:
            convs = []
        return templates.TemplateResponse(
            request=request,
            name="history.html",
            context={"conversations": convs},
        )

    @app.get("/_partials/current-model", response_class=HTMLResponse)
    async def current_model(request: Request):
        try:
            r = await app.state.client.get("/admin/stats")
            current = r.json().get("current_model")
        except Exception:
            current = None
        return templates.TemplateResponse(
            request=request,
            name="_partials/current_model.html",
            context={"current_model": current},
        )

    @app.post("/chat/send", response_class=HTMLResponse)
    async def chat_send(request: Request):
        form = await request.form()
        prompt = str(form.get("prompt", "")).strip()
        conversation_id = str(form.get("conversation_id", "")).strip()
        if not conversation_id:
            stats = (await app.state.client.get("/admin/stats")).json()
            model_id = stats.get("current_model") or "unknown"
            r = await app.state.client.post(
                "/history/conversations",
                json={"title": prompt[:60] or "new chat", "model_id": model_id},
            )
            conversation_id = r.json()["id"]
        await app.state.client.post(
            "/history/messages",
            json={"conversation_id": conversation_id, "role": "user", "content": prompt},
        )
        # Return both bubbles concatenated; HTMX appends to #messages.
        user_html = templates.get_template("_partials/user_msg.html").render(content=prompt)
        shell_html = templates.get_template("_partials/assistant_shell.html").render(
            conversation_id=conversation_id, prompt=prompt
        )
        return HTMLResponse(user_html + shell_html)

    @app.get("/chat/stream")
    async def chat_stream(prompt: str, conversation_id: str):
        async def relay():
            payload = {
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
            }
            full_text: list[str] = []
            final_stats: dict | None = None
            async with app.state.client.stream("POST", "/v1/chat/completions", json=payload) as r:
                async for raw in r.aiter_lines():
                    if not raw.startswith("data: "):
                        continue
                    data = raw[len("data: ") :]
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full_text.append(content)
                        yield f"event: message\ndata: {content}\n\n"
                    if "x_local_model_stats" in chunk:
                        final_stats = chunk["x_local_model_stats"]
            if final_stats is not None:
                yield (
                    "event: stats\n"
                    f"data: ttft {final_stats['ttft_ms']:.0f}ms · "
                    f"{final_stats['tps']:.1f} tok/s\n\n"
                )
            # Sentinel event — htmx-ext-sse closes the EventSource on receipt,
            # preventing the browser's default auto-reconnect.
            yield "event: done\ndata: end\n\n"
            # Persist the assistant message after the stream finishes
            try:
                await app.state.client.post(
                    "/history/messages",
                    json={
                        "conversation_id": conversation_id,
                        "role": "assistant",
                        "content": "".join(full_text),
                    },
                )
            except Exception as e:
                logger.warning("Failed to persist assistant message: %s", e)

        return StreamingResponse(relay(), media_type="text/event-stream")

    @app.get("/presets", response_class=HTMLResponse)
    async def presets_page(request: Request):
        r = await app.state.client.get("/presets")
        presets = r.json() if r.status_code == 200 else []
        return templates.TemplateResponse(
            request=request,
            name="presets.html",
            context={"presets": presets},
        )

    @app.post("/presets/new", response_class=HTMLResponse)
    async def presets_new(request: Request):
        form = await request.form()
        r = await app.state.client.post(
            "/presets",
            json={
                "name": str(form["name"]),
                "system_prompt": str(form["system_prompt"]),
                "default_params": {},
            },
        )
        p = r.json()
        return HTMLResponse(f"<li><strong>{p['name']}</strong>: {p['system_prompt'][:100]}</li>")

    @app.get("/stats", response_class=HTMLResponse)
    async def stats_page(request: Request):
        stats_r = await app.state.client.get("/admin/stats")
        models_r = await app.state.client.get("/v1/models")
        return templates.TemplateResponse(
            request=request,
            name="stats.html",
            context={
                "stats": stats_r.json(),
                "models": models_r.json().get("data", []),
            },
        )

    @app.post("/swap", response_class=HTMLResponse)
    async def swap(request: Request):
        form = await request.form()
        r = await app.state.client.post(
            "/admin/models/load", json={"model_id": str(form["model_id"])}
        )
        info = r.json()
        return HTMLResponse(f"<span>model: {info['id']}</span>")

    app.mount("/static", StaticFiles(directory=str(base / "static")), name="static")
    return app


def build_app_from_env() -> FastAPI:
    settings = ClientSettings()
    logging.basicConfig(level="INFO")
    primary = settings.endpoints[0]
    return create_app(server_url=primary["url"])
