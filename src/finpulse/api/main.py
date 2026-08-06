from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from finpulse import __version__
from finpulse.config import get_settings
from finpulse.logging import configure_logging

LOGGER = logging.getLogger(__name__)
settings = get_settings()
configure_logging(settings.log_level)

REQUESTS = Counter("finpulse_api_requests_total", "API requests", ["endpoint", "status"])
QUERY_DURATION = Histogram(
    "finpulse_api_query_duration_seconds", "Warehouse query latency", ["endpoint"]
)
LATEST_EVENT_AGE = Gauge(
    "finpulse_latest_event_age_seconds", "Age of the most recently ingested event"
)
TOTAL_EVENTS = Gauge("finpulse_warehouse_events_total", "Events loaded into the warehouse")
QUARANTINE_RATE = Gauge("finpulse_quarantine_rate", "Latest pipeline quarantine rate as a fraction")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    pool = AsyncConnectionPool(
        conninfo=settings.warehouse_dsn,
        min_size=1,
        max_size=10,
        timeout=10,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    await pool.open(wait=True)
    app.state.pool = pool
    LOGGER.info("API database pool opened")
    try:
        yield
    finally:
        await pool.close()
        LOGGER.info("API database pool closed")


app = FastAPI(
    title="FinPulse Data Platform API",
    summary="Operational and analytical API for the credit data product",
    description=(
        "Read-only serving layer over curated portfolio marts. All customer identifiers are "
        "pseudonymised before reaching this interface."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


async def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    async with app.state.pool.connection() as connection, connection.cursor() as cursor:
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    rows = await fetch_all(query, params)
    return rows[0] if rows else {}


@app.get("/health", tags=["platform"])
async def health(response: Response) -> dict[str, Any]:
    try:
        result = await fetch_one("SELECT NOW() AS database_time")
        REQUESTS.labels(endpoint="health", status="200").inc()
        return {
            "status": "healthy",
            "service": "finpulse-api",
            "version": __version__,
            "database_time": result.get("database_time"),
            "checked_at": datetime.now(UTC),
        }
    except Exception as exc:
        LOGGER.exception("health check failed")
        REQUESTS.labels(endpoint="health", status="503").inc()
        response.status_code = 503
        return {"status": "unhealthy", "reason": type(exc).__name__}


@app.get("/api/v1/summary", tags=["portfolio"])
async def summary() -> dict[str, Any]:
    with QUERY_DURATION.labels(endpoint="summary").time():
        data = await fetch_one("SELECT * FROM analytics.vw_realtime_kpis")
        event_data = await fetch_one(
            """
            SELECT COUNT(*) AS total_events, MAX(ingested_at) AS latest_event_at,
                   COUNT(*) FILTER (WHERE ingested_at >= NOW() - INTERVAL '5 minutes') AS events_5m
            FROM warehouse.event_fact
            """
        )
    latest = event_data.get("latest_event_at")
    if latest:
        LATEST_EVENT_AGE.set(max(0, (datetime.now(UTC) - latest).total_seconds()))
    TOTAL_EVENTS.set(event_data.get("total_events", 0))
    REQUESTS.labels(endpoint="summary", status="200").inc()
    return {**data, **event_data, "generated_at": datetime.now(UTC)}


@app.get("/api/v1/countries", tags=["portfolio"])
async def country_performance() -> list[dict[str, Any]]:
    with QUERY_DURATION.labels(endpoint="countries").time():
        rows = await fetch_all(
            "SELECT * FROM analytics.vw_country_performance ORDER BY country_code"
        )
    REQUESTS.labels(endpoint="countries", status="200").inc()
    return rows


@app.get("/api/v1/throughput", tags=["platform"])
async def throughput(minutes: int = Query(default=60, ge=5, le=1_440)) -> list[dict[str, Any]]:
    with QUERY_DURATION.labels(endpoint="throughput").time():
        rows = await fetch_all(
            """
            SELECT minute, event_type, SUM(event_count) AS event_count,
                   ROUND(AVG(avg_lag_seconds), 3) AS avg_lag_seconds,
                   MAX(p95_lag_seconds) AS p95_lag_seconds
            FROM analytics.vw_event_throughput
            WHERE minute >= NOW() - (%s * INTERVAL '1 minute')
            GROUP BY minute, event_type
            ORDER BY minute, event_type
            """,
            (minutes,),
        )
    REQUESTS.labels(endpoint="throughput", status="200").inc()
    return rows


@app.get("/api/v1/events/recent", tags=["platform"])
async def recent_events(limit: int = Query(default=25, ge=1, le=200)) -> list[dict[str, Any]]:
    rows = await fetch_all(
        """
        SELECT event_id, event_type, occurred_at, ingested_at, source_system, country_code,
               LEFT(customer_id::text, 8) || '…' AS customer_token,
               ROUND(EXTRACT(EPOCH FROM (ingested_at - occurred_at))::numeric, 3) AS lag_seconds,
               trace_id
        FROM warehouse.event_fact
        ORDER BY ingested_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    return rows


@app.get("/api/v1/risk-distribution", tags=["portfolio"])
async def risk_distribution() -> list[dict[str, Any]]:
    return await fetch_all(
        """
        SELECT
            CASE
                WHEN score < 450 THEN 'very_high'
                WHEN score < 550 THEN 'high'
                WHEN score < 650 THEN 'medium'
                WHEN score < 750 THEN 'low'
                ELSE 'very_low'
            END AS risk_band,
            COUNT(*) AS decisions,
            ROUND(AVG(score), 1) AS average_score,
            ROUND(100.0 * COUNT(*) FILTER (WHERE decision = 'approved') / COUNT(*), 2)
                AS approval_rate_pct
        FROM warehouse.loan_decisions
        GROUP BY 1
        ORDER BY MIN(score)
        """
    )


@app.get("/api/v1/model-monitoring", tags=["risk"])
async def model_monitoring() -> list[dict[str, Any]]:
    return await fetch_all(
        """
        SELECT
            DATE_TRUNC('hour', occurred_at) AS period,
            model_version,
            COUNT(*) AS decisions,
            ROUND(AVG(score), 1) AS average_score,
            ROUND(STDDEV_POP(score), 2) AS score_stddev,
            ROUND(100.0 * COUNT(*) FILTER (WHERE decision = 'approved') / COUNT(*), 2)
                AS approval_rate_pct
        FROM warehouse.loan_decisions
        GROUP BY 1, 2
        ORDER BY 1
        """
    )


@app.get("/api/v1/data-quality", tags=["platform"])
async def data_quality() -> dict[str, Any]:
    rules = await fetch_all(
        """
        SELECT dataset_name, rule_name, status, observed_value, threshold_value, checked_at
        FROM observability.data_quality_results
        ORDER BY checked_at DESC
        LIMIT 50
        """
    )
    pipeline = await fetch_one(
        """
        SELECT pipeline_name, status, started_at, completed_at, input_rows, output_rows,
               quarantined_rows, metadata
        FROM observability.pipeline_runs
        ORDER BY started_at DESC
        LIMIT 1
        """
    )
    if pipeline.get("input_rows"):
        QUARANTINE_RATE.set((pipeline.get("quarantined_rows") or 0) / pipeline["input_rows"])
    return {"latest_pipeline_run": pipeline or None, "checks": rules}


@app.get("/api/v1/lineage", tags=["platform"])
async def lineage() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "gsm-mobile-money", "label": "GSM + Mobile Money", "type": "source"},
            {"id": "kafka", "label": "Kafka / Redpanda", "type": "stream"},
            {"id": "spark", "label": "Spark Structured Streaming", "type": "processor"},
            {"id": "s3", "label": "S3 Medallion Lakehouse", "type": "storage"},
            {"id": "warehouse", "label": "Redshift-compatible Warehouse", "type": "warehouse"},
            {"id": "dbt", "label": "dbt Credit Marts", "type": "transformation"},
            {"id": "serving", "label": "API + BI + Risk Features", "type": "product"},
        ],
        "edges": [
            ["gsm-mobile-money", "kafka"],
            ["kafka", "spark"],
            ["spark", "s3"],
            ["spark", "warehouse"],
            ["warehouse", "dbt"],
            ["dbt", "serving"],
        ],
    }


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    try:
        data = await fetch_one(
            "SELECT COUNT(*) AS event_count, MAX(ingested_at) AS latest FROM warehouse.event_fact"
        )
        TOTAL_EVENTS.set(data.get("event_count", 0))
        if data.get("latest"):
            LATEST_EVENT_AGE.set(max(0, (datetime.now(UTC) - data["latest"]).total_seconds()))
    except Exception:
        LOGGER.warning("could not refresh warehouse metrics", exc_info=True)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.exception_handler(Exception)
async def unhandled_exception(_request: Request, exc: Exception) -> Response:
    LOGGER.exception("unhandled API exception", exc_info=exc)
    return Response(
        content='{"detail":"internal platform error"}',
        status_code=500,
        media_type="application/json",
    )


def run() -> None:
    import uvicorn

    uvicorn.run("finpulse.api.main:app", host="0.0.0.0", port=8000)
