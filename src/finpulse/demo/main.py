from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from finpulse.contracts import EventType
from finpulse.demo.engine import (
    COUNTRIES,
    DemoError,
    event_detail,
    event_page,
    export_csv,
    initialize,
    process,
    replay,
    simulate,
    snapshot,
)
from finpulse.demo.store import WorkspaceStore


def create_app(
    data_dir: Path | str | None = None,
    public_origin: str | None = None,
    cookie_path: str | None = None,
    max_sessions: int = 40,
    ttl: int = 7200,
    web_dist: Path | None = None,
) -> FastAPI:
    origin = (
        public_origin if public_origin is not None else os.getenv("PUBLIC_ORIGIN", "")
    ).rstrip("/")
    if origin:
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError(
                "PUBLIC_ORIGIN must be an HTTP(S) origin without credentials or a path"
            )
    cookie_scope = cookie_path or os.getenv("COOKIE_PATH", "/finpulse")
    directory = Path(data_dir or os.getenv("FINPULSE_DATA_DIR", "artifacts/web-demo"))
    frontend = web_dist or Path(
        os.getenv("FINPULSE_WEB_DIST", Path(__file__).resolve().parents[3] / "web" / "dist")
    )
    store = WorkspaceStore(directory, max_sessions=max_sessions, ttl=ttl)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        store.close()

    app = FastAPI(
        title="FinPulse synthetic sandbox",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.store = store

    @app.middleware("http")
    async def guard(request: Request, call_next):
        sid = None
        try:
            if request.url.path.startswith("/api/") and request.url.path != "/api/health":
                mutation = request.method not in {"GET", "HEAD", "OPTIONS"}
                if mutation:
                    received_origin = request.headers.get("origin")
                    expected_origin = origin or str(request.base_url).rstrip("/")
                    if (
                        received_origin and received_origin != expected_origin
                    ) or request.headers.get("sec-fetch-site") == "cross-site":
                        raise DemoError("Cross-site mutations are not allowed.", 403)
                    if (
                        request.headers.get("content-type", "").split(";", 1)[0].lower()
                        != "application/json"
                    ):
                        raise DemoError("Send application/json for demo changes.", 415)
                    body = bytearray()
                    async for chunk in request.stream():
                        body.extend(chunk)
                        if len(body) > 8192:
                            raise DemoError("Request exceeds the 8 KB demo input limit.", 413)
                    request._body = bytes(body)
                sid = await run_in_threadpool(
                    store.session,
                    request.cookies.get("finpulse_session"),
                    request.client.host if request.client else "unknown",
                    mutation,
                )
                request.state.sid = sid
            response = await call_next(request)
        except DemoError as exc:
            response = JSONResponse({"error": str(exc)}, status_code=exc.status)
        except sqlite3.Error:
            response = JSONResponse(
                {
                    "error": (
                        "Demo storage is temporarily unavailable. "
                        "No uncommitted changes were applied."
                    )
                },
                status_code=503,
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if sid:
            response.set_cookie(
                "finpulse_session",
                sid,
                max_age=ttl,
                httponly=True,
                secure=origin.startswith("https:") or request.url.scheme == "https",
                samesite="lax",
                path=cookie_scope,
            )
        return response

    @app.exception_handler(DemoError)
    async def demo_error(_request, exc):
        return JSONResponse({"error": str(exc)}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def request_error(_request, _exc):
        return JSONResponse(
            {"error": "The request body or query parameters are invalid."}, status_code=400
        )

    @app.exception_handler(Exception)
    async def unknown_error(_request, _exc):
        return JSONResponse(
            {"error": "The demo could not complete this request. Please retry."}, status_code=500
        )

    def country(request: Request):
        value = request.query_params.get("country")
        if value and value not in {item["code"] for item in COUNTRIES}:
            raise DemoError("Country must be KEN, UGA, GHA, TZA or ZMB.")
        return value

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "mode": "synthetic",
            "storage": "sqlite",
            "version": "2.0.0",
            "engine": "original contracts + quality rules + SQLite",
        }

    @app.get("/api/workspace")
    def workspace(request: Request):
        with store.workspace(request.state.sid) as db:
            return snapshot(db, country(request))

    @app.get("/api/events")
    def events(request: Request):
        try:
            limit, offset = (
                int(request.query_params.get("limit", "250")),
                int(request.query_params.get("offset", "0")),
            )
        except ValueError as exc:
            raise DemoError("Pagination values must be integers.") from exc
        if not 1 <= limit <= 250 or not 0 <= offset <= 2500:
            raise DemoError("Use a limit from 1 to 250 and an offset from 0 to 2,500.")
        status = request.query_params.get("status")
        event_type = request.query_params.get("type")
        if status and status not in {"pending", "accepted", "quarantined", "duplicate", "replayed"}:
            raise DemoError("Unknown delivery status.")
        if event_type and event_type not in {item.value for item in EventType}:
            raise DemoError("Unknown event type.")
        with store.workspace(request.state.sid) as db:
            return event_page(db, country(request), status, event_type, limit, offset)

    @app.get("/api/events/{delivery_id}")
    def detail(request: Request, delivery_id: str):
        with store.workspace(request.state.sid) as db:
            return event_detail(db, delivery_id)

    @app.post("/api/simulate")
    def simulation(request: Request, body: dict):
        if set(body) - {"scenario", "count"}:
            raise DemoError(
                "Only scenario and count may be supplied; arbitrary event ingestion is disabled."
            )
        with store.workspace(request.state.sid) as db:
            operation = simulate(db, body.get("scenario"), body.get("count", 20))
            return snapshot(db, country(request), operation)

    @app.post("/api/pipeline/run")
    def pipeline(request: Request, body: dict):
        if body:
            raise DemoError("Pipeline execution accepts an empty JSON object only.")
        with store.workspace(request.state.sid) as db:
            operation = process(db)
            return snapshot(db, country(request), operation)

    @app.post("/api/quarantine/{delivery_id}/replay")
    def replay_event(request: Request, delivery_id: str, body: dict):
        if set(body) - {"decision"}:
            raise DemoError("Only the displayed server-recorded correction may be approved.")
        with store.workspace(request.state.sid) as db:
            operation = replay(db, delivery_id, body.get("decision"))
            return snapshot(db, country(request), operation)

    @app.post("/api/reset")
    def reset(request: Request, body: dict):
        if body:
            raise DemoError("Reset accepts an empty JSON object only.")
        with store.workspace(request.state.sid) as db:
            tables = [
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            ]
            for table in tables:
                db.execute(f'DELETE FROM "{table}"')
            initialize(db, create_schema=False)
            return snapshot(db, operation={"type": "reset"})

    @app.get("/api/export")
    def export(request: Request):
        dataset = request.query_params.get("dataset", "events")
        with store.workspace(request.state.sid) as db:
            csv = export_csv(db, dataset, country(request))
        return Response(
            csv,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="finpulse-synthetic-{dataset}.csv"'
            },
        )

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def missing_api(path: str):
        raise DemoError("API endpoint not found.", 404)

    @app.get("/{path:path}")
    def frontend_file(path: str):
        resolved_root = frontend.resolve()
        candidate = (resolved_root / path).resolve()
        if candidate.is_relative_to(resolved_root) and candidate.is_file():
            return FileResponse(candidate)
        if "." in Path(path).name:
            return JSONResponse({"error": "Asset not found."}, status_code=404)
        index = resolved_root / "index.html"
        if not index.exists():
            return JSONResponse(
                {"error": "Frontend build not present. Run npm run build inside web/."},
                status_code=503,
            )
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
