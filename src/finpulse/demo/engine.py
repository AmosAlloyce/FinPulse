from __future__ import annotations

import copy
import csv
import io
import json
import sqlite3
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from finpulse.contracts import EventEnvelope
from finpulse.generator import CURRENCIES, SyntheticEventGenerator
from finpulse.local_pipeline import LOCAL_SCHEMA, LocalPipeline
from finpulse.quality import QualityIssue, QualityReport, validate_business_rules

MAX_EVENTS = 2500
MAX_BATCH = 100
MAX_RUNS = 40
COUNTRIES = [
    {"code": "KEN", "name": "Kenya", "currency": "KES"},
    {"code": "UGA", "name": "Uganda", "currency": "UGX"},
    {"code": "GHA", "name": "Ghana", "currency": "GHS"},
    {"code": "TZA", "name": "Tanzania", "currency": "TZS"},
    {"code": "ZMB", "name": "Zambia", "currency": "ZMW"},
]
RULES = [
    {
        "id": "schema_contract",
        "label": "Versioned event contract",
        "severity": "error",
        "description": (
            "Seven discriminated payload types, UUIDs, timezone-aware timestamps, "
            "ranges and exact fields."
        ),
        "implementation": "finpulse.contracts.EventEnvelope",
    },
    {
        "id": "event_not_in_future",
        "label": "Event-time sanity",
        "severity": "error",
        "description": "Occurrence cannot be more than five minutes ahead of the validator clock.",
        "implementation": "finpulse.quality.validate_business_rules",
    },
    {
        "id": "ingestion_after_occurrence",
        "label": "Ingestion order",
        "severity": "error",
        "description": "Ingestion timestamp must follow occurrence.",
        "implementation": "finpulse.quality.validate_business_rules",
    },
    {
        "id": "freshness_24h",
        "label": "24-hour freshness",
        "severity": "warning",
        "description": "Events arriving over 24 hours late remain accepted and receive a warning.",
        "implementation": "finpulse.quality.validate_business_rules",
    },
    {
        "id": "declined_amount_zero",
        "label": "Decision amount consistency",
        "severity": "error",
        "description": "A synthetic non-approved decision must have zero approved amount.",
        "implementation": "finpulse.quality.validate_business_rules",
    },
    {
        "id": "repayment_status_consistency",
        "label": "Repayment consistency",
        "severity": "error",
        "description": "Late or partial payments require positive days past due.",
        "implementation": "finpulse.quality.validate_business_rules",
    },
    {
        "id": "event_id_unique",
        "label": "Idempotent delivery",
        "severity": "info",
        "description": (
            "Repeat delivery of an accepted event ID does not create another warehouse fact."
        ),
        "implementation": "LOCAL_SCHEMA.event_fact primary key",
    },
]
LINEAGE = {
    "nodes": [
        {"id": key, "label": label, "kind": kind}
        for key, label, kind in [
            ("sources", "Synthetic sources", "source"),
            ("bronze", "Immutable deliveries", "dataset"),
            ("contract", "Contract + quality gate", "transformation"),
            ("quarantine", "Inspectable quarantine", "dataset"),
            ("silver", "Typed event facts", "dataset"),
            ("portfolio", "Application portfolio", "product"),
            ("countries", "Country performance", "product"),
            ("features", "Customer features", "product"),
        ]
    ],
    "edges": [
        ["sources", "bronze"],
        ["bronze", "contract"],
        ["contract", "quarantine"],
        ["contract", "silver"],
        ["silver", "portfolio"],
        ["portfolio", "countries"],
        ["silver", "features"],
    ],
}
DEMO_SCHEMA = """
CREATE TABLE IF NOT EXISTS demo_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS demo_deliveries (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
 event_id TEXT NOT NULL, event_type TEXT NOT NULL, country_code TEXT NOT NULL,
 customer_id TEXT NOT NULL, raw TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 issues TEXT NOT NULL DEFAULT '[]', correction TEXT, corrected_raw TEXT,
 run_id TEXT, late INTEGER NOT NULL DEFAULT 0, replay_id TEXT,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS demo_delivery_status ON demo_deliveries(status);
CREATE TABLE IF NOT EXISTS demo_runs (id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS demo_audit (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL);
"""


class DemoError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def scalar(db: sqlite3.Connection, query: str, args: tuple = ()) -> Any:
    row = db.execute(query, args).fetchone()
    return row[0] if row and row[0] is not None else 0


def meta(db: sqlite3.Connection, key: str) -> Any:
    return json.loads(db.execute("SELECT value FROM demo_meta WHERE key=?", (key,)).fetchone()[0])


def set_meta(db: sqlite3.Connection, key: str, value: Any) -> None:
    db.execute("INSERT OR REPLACE INTO demo_meta VALUES (?,?)", (key, json.dumps(value)))


def audit(db: sqlite3.Connection, action: str, detail: str) -> None:
    db.execute(
        "INSERT INTO demo_audit(body) VALUES (?)",
        (
            json.dumps(
                {"id": str(uuid4()), "action": action, "detail": detail, "createdAt": now_iso()}
            ),
        ),
    )
    db.execute(
        "DELETE FROM demo_audit WHERE sequence NOT IN "
        "(SELECT sequence FROM demo_audit ORDER BY sequence DESC LIMIT 100)"
    )


def stage(
    db: sqlite3.Connection, raw: dict, correction: dict | None = None, original: dict | None = None
) -> str:
    delivery_id = str(uuid4())
    db.execute(
        """INSERT INTO demo_deliveries(
                  id,event_id,event_type,country_code,customer_id,raw,
                  correction,corrected_raw,created_at)
                  VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            delivery_id,
            raw["event_id"],
            raw["event_type"],
            raw["country_code"],
            raw["customer_id"],
            json.dumps(raw),
            json.dumps(correction) if correction else None,
            json.dumps(original) if original else None,
            now_iso(),
        ),
    )
    return delivery_id


def generated_batch(db: sqlite3.Connection, count: int) -> list[dict]:
    cursor = meta(db, "generatorCursor")
    generator = SyntheticEventGenerator(
        seed=meta(db, "seed"), start_time=datetime.fromisoformat(meta(db, "startTime"))
    )
    # Reconstruction preserves the generator's customer/application relationships.
    for _ in range(cursor):
        generator.next_event()
    result = [event.model_dump(mode="json") for event in generator.events(count)]
    set_meta(db, "generatorCursor", cursor + count)
    return result


def inject_invalid(raw: dict, index: int) -> tuple[dict, dict]:
    broken = copy.deepcopy(raw)
    variant = index % 3
    if variant == 0:
        field, before, after = "schema_version", "0.0", raw["schema_version"]
        broken[field] = before
        description = (
            "Restore the original generated schema version; no business values are inferred."
        )
    elif variant == 1:
        field, after = "ingested_at", raw["ingested_at"]
        before = (
            datetime.fromisoformat(raw["occurred_at"].replace("Z", "+00:00")) - timedelta(seconds=5)
        ).isoformat()
        broken[field] = before
        description = "Restore the original generated ingestion timestamp."
    else:
        field, after = "occurred_at", raw["occurred_at"]
        before = (datetime.now(UTC) + timedelta(days=2)).isoformat()
        broken[field] = before
        description = "Restore the original generated occurrence timestamp."
    return broken, {"field": field, "before": before, "after": after, "description": description}


def simulate(db: sqlite3.Connection, scenario: str, count: int) -> dict:
    if (
        not isinstance(scenario, str)
        or scenario not in {"normal", "duplicates", "invalid", "late"}
        or isinstance(count, bool)
        or not isinstance(count, int)
        or not 1 <= count <= MAX_BATCH
    ):
        raise DemoError(
            "Choose normal, duplicates, invalid or late and an integer count from 1 to 100."
        )
    # Leave capacity for a future correction of every open quarantine record.
    reserved = scalar(
        db,
        "SELECT COUNT(*) FROM demo_deliveries WHERE corrected_raw IS NOT NULL "
        "AND status IN ('pending','quarantined')",
    )
    required = count + reserved + (count if scenario == "invalid" else 0)
    if scalar(db, "SELECT COUNT(*) FROM demo_deliveries") + required > MAX_EVENTS:
        raise DemoError(
            "This workspace reached its 2,500-delivery limit. "
            "Reset the synthetic demo to continue.",
            429,
        )
    if scenario == "duplicates":
        sources = db.execute(
            "SELECT raw FROM demo_deliveries WHERE status='accepted' ORDER BY sequence LIMIT 100"
        ).fetchall()
        if not sources:
            raise DemoError("Process an accepted event before simulating duplicate delivery.", 409)
        for i in range(count):
            stage(db, json.loads(sources[i % len(sources)][0]))
    else:
        for i, raw in enumerate(generated_batch(db, count)):
            if scenario == "invalid":
                broken, correction = inject_invalid(raw, i)
                stage(db, broken, correction, raw)
            elif scenario == "late":
                late = copy.deepcopy(raw)
                late["occurred_at"] = (
                    datetime.fromisoformat(raw["occurred_at"].replace("Z", "+00:00"))
                    - timedelta(days=2)
                ).isoformat()
                stage(db, late)
            else:
                stage(db, raw)
    set_meta(db, "revision", meta(db, "revision") + 1)
    audit(
        db,
        "Synthetic deliveries staged",
        f"{count} {scenario} deliveries added to bronze. "
        "Warehouse facts remain unchanged until a pipeline run.",
    )
    return {
        "type": "simulation",
        "scenario": scenario,
        "count": count,
        "pending": scalar(db, "SELECT COUNT(*) FROM demo_deliveries WHERE status='pending'"),
    }


def process(db: sqlite3.Connection, trigger: str = "manual", only: str | None = None) -> dict:
    started = time.perf_counter()
    if scalar(db, "SELECT COUNT(*) FROM demo_runs") >= MAX_RUNS:
        raise DemoError("This demo reached its 40-run limit. Reset the workspace to continue.", 429)
    rows = db.execute(
        "SELECT * FROM demo_deliveries WHERE status='pending'"
        + (" AND id=?" if only else "")
        + " ORDER BY sequence",
        (only,) if only else (),
    ).fetchall()
    if not rows:
        raise DemoError("No pending deliveries. Simulate a batch first.", 409)
    bronze_ms = round((time.perf_counter() - started) * 1000, 2)
    run_id = "RUN-" + uuid4().hex[:8].upper()
    report = QualityReport()
    loader = LocalPipeline(Path("."))
    parsed = []
    schema_started = time.perf_counter()
    for row in rows:
        report.received += 1
        try:
            event = EventEnvelope.from_json(row["raw"])
            parsed.append((row, event))
        except (ValidationError, ValueError):
            issue = QualityIssue(
                "schema_contract",
                "error",
                "Event failed the original versioned Pydantic contract. "
                "Restore the known injected field to replay.",
                row["event_id"],
            )
            report.issues.append(issue)
            report.quarantined += 1
            db.execute(
                "UPDATE demo_deliveries SET status='quarantined',issues=?,run_id=? WHERE id=?",
                (json.dumps([asdict(issue)]), run_id, row["id"]),
            )
    schema_ms = round((time.perf_counter() - schema_started) * 1000, 2)
    quality_started = time.perf_counter()
    load_ms = 0.0
    valid = []
    for row, event in parsed:
        if db.execute(
            "SELECT 1 FROM event_fact WHERE event_id=?", (str(event.event_id),)
        ).fetchone():
            report.duplicates += 1
            db.execute(
                "UPDATE demo_deliveries SET status='duplicate',run_id=? WHERE id=?",
                (run_id, row["id"]),
            )
            continue
        issues = validate_business_rules(event, now=datetime.now(UTC))
        report.issues.extend(issues)
        if any(issue.severity == "error" for issue in issues):
            report.quarantined += 1
            db.execute(
                "UPDATE demo_deliveries SET status='quarantined',issues=?,run_id=? WHERE id=?",
                (json.dumps([asdict(issue) for issue in issues]), run_id, row["id"]),
            )
            continue
        late = any(issue.rule == "freshness_24h" for issue in issues)
        report.late_events += int(late)
        # Use the original dimensional loader; its event_fact primary key protects all paths.
        load_started = time.perf_counter()
        loader._load_event(db, event)
        load_ms += (time.perf_counter() - load_started) * 1000
        report.accepted += 1
        valid.append(event)
        db.execute(
            "UPDATE demo_deliveries SET status='accepted',issues=?,run_id=?,late=? WHERE id=?",
            (json.dumps([asdict(issue) for issue in issues]), run_id, int(late), row["id"]),
        )
    loader._record_issues(db, report.issues)
    quality_ms = round(max(0, (time.perf_counter() - quality_started) * 1000 - load_ms), 2)
    mart_started = time.perf_counter()
    summary = loader._summary(db, run_id, report)
    portfolio_rows = scalar(db, "SELECT COUNT(*) FROM mart_application_portfolio")
    country_rows = scalar(db, "SELECT COUNT(*) FROM mart_country_performance")
    mart_ms = round((time.perf_counter() - mart_started) * 1000, 2)
    counts = {
        "received": report.received,
        "accepted": report.accepted,
        "quarantined": report.quarantined,
        "duplicates": report.duplicates,
        "late": report.late_events,
    }
    run = {
        "id": run_id,
        "status": "completed",
        "trigger": trigger,
        "createdAt": now_iso(),
        "durationMs": round((time.perf_counter() - started) * 1000, 2),
        "counts": counts,
        "steps": [
            {
                "id": "bronze",
                "label": "Read immutable deliveries",
                "status": "complete",
                "count": len(rows),
                "detail": f"Selected {len(rows)} pending synthetic deliveries from SQLite bronze.",
                "durationMs": bronze_ms,
            },
            {
                "id": "contract",
                "label": "Validate event contracts",
                "status": "warning" if len(parsed) < len(rows) else "complete",
                "count": len(parsed),
                "detail": (
                    f"Original EventEnvelope accepted {len(parsed)} of {len(rows)} contracts."
                ),
                "durationMs": schema_ms,
            },
            {
                "id": "quality",
                "label": "Apply quality + deduplication",
                "status": "warning" if report.quarantined else "complete",
                "count": report.accepted,
                "detail": (
                    f"{report.accepted} accepted, {report.quarantined} quarantined, "
                    f"{report.duplicates} duplicate deliveries suppressed; "
                    f"{report.late_events} late events retained with warnings."
                ),
                "durationMs": quality_ms,
            },
            {
                "id": "silver",
                "label": "Load typed event facts",
                "status": "complete",
                "count": report.accepted,
                "detail": (
                    "Original LocalPipeline dimensional loader populated event facts "
                    "and domain tables in this transaction."
                ),
                "durationMs": round(load_ms, 2),
            },
            {
                "id": "gold",
                "label": "Refresh governed marts",
                "status": "complete",
                "count": portfolio_rows,
                "detail": (
                    f"Queried {portfolio_rows} application rows and {country_rows} country rows "
                    "from the original SQL views. Money remains grouped by currency."
                ),
                "durationMs": mart_ms,
            },
        ],
        "businessMetrics": summary["business_metrics"],
    }
    db.execute("INSERT INTO demo_runs VALUES (?,?)", (run_id, json.dumps(run)))
    db.execute(
        "INSERT INTO pipeline_runs VALUES (?,?,?,?,?,?,?)",
        (
            run_id,
            run["createdAt"],
            now_iso(),
            report.received,
            report.accepted,
            report.quarantined,
            report.duplicates,
        ),
    )
    set_meta(db, "revision", meta(db, "revision") + 1)
    audit(
        db,
        "Pipeline completed",
        f"{run_id}: {report.accepted} accepted; {report.quarantined} quarantined; "
        f"{report.duplicates} duplicates suppressed.",
    )
    return {"type": "pipeline", "runId": run_id, "counts": counts}


def initialize(db: sqlite3.Connection, create_schema: bool = True) -> None:
    if create_schema:
        db.executescript(LOCAL_SCHEMA + DEMO_SCHEMA)
    for key, value in {
        "seed": 42,
        "generatorCursor": 0,
        "startTime": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
        "createdAt": now_iso(),
        "revision": 0,
    }.items():
        set_meta(db, key, value)
    for raw in generated_batch(db, 960):
        stage(db, raw)
    process(db, "initial_seed")
    simulate(db, "duplicates", 8)
    simulate(db, "invalid", 6)
    simulate(db, "late", 6)
    process(db, "quality_rehearsal")


def replay(db: sqlite3.Connection, delivery_id: str, decision: Any) -> dict:
    if decision != "approve":
        raise DemoError(
            "Explicit decision:'approve' is required to apply the displayed known correction."
        )
    row = db.execute("SELECT * FROM demo_deliveries WHERE id=?", (delivery_id,)).fetchone()
    if not row:
        raise DemoError("Quarantined delivery not found in this workspace.", 404)
    if row["status"] != "quarantined" or row["replay_id"]:
        raise DemoError("This delivery is not awaiting replay, or has already been replayed.", 409)
    if not row["correction"] or not row["corrected_raw"]:
        raise DemoError(
            "No trusted original value is available; arbitrary corrections are not accepted.", 409
        )
    if scalar(db, "SELECT COUNT(*) FROM demo_deliveries") >= MAX_EVENTS:
        raise DemoError("Workspace delivery limit reached. Reset the demo to continue.", 429)
    corrected = EventEnvelope.from_json(row["corrected_raw"])
    if any(issue.severity == "error" for issue in validate_business_rules(corrected)):
        raise DemoError(
            "The original value no longer passes validation. Reset the demo to continue.", 409
        )
    if db.execute("SELECT 1 FROM event_fact WHERE event_id=?", (row["event_id"],)).fetchone():
        raise DemoError(
            "This event ID is already loaded. No additional fact will be inserted.", 409
        )
    new_id = stage(db, corrected.model_dump(mode="json"))
    operation = process(db, "approved_replay", only=new_id)
    db.execute(
        "UPDATE demo_deliveries SET status='replayed',replay_id=? WHERE id=?", (new_id, delivery_id)
    )
    audit(
        db,
        "Known correction approved",
        f"Replayed {delivery_id} as {new_id}; "
        f"restored only {json.loads(row['correction'])['field']}. "
        "Original raw delivery preserved.",
    )
    return {
        "type": "replay",
        "id": delivery_id,
        "replayEventId": new_id,
        "runId": operation["runId"],
    }


def event_view(row: sqlite3.Row) -> dict:
    raw = json.loads(row["raw"])
    payload = raw.get("payload", {})
    return {
        "id": row["id"],
        "eventId": row["event_id"],
        "eventType": row["event_type"],
        "source": raw["source_system"],
        "countryCode": row["country_code"],
        "currency": payload.get("currency")
        or (CURRENCIES[row["country_code"]] if "approved_amount" in payload else None),
        "amount": payload.get(
            "amount", payload.get("requested_amount", payload.get("approved_amount"))
        ),
        "customerId": row["customer_id"],
        "occurredAt": raw["occurred_at"],
        "ingestedAt": raw["ingested_at"],
        "status": row["status"],
        "late": bool(row["late"]),
        "issues": json.loads(row["issues"]),
        "runId": row["run_id"],
        "sequence": row["sequence"],
    }


def event_page(
    db: sqlite3.Connection,
    country: str | None = None,
    status: str | None = None,
    event_type: str | None = None,
    limit: int = 250,
    offset: int = 0,
) -> dict:
    clauses, args = [], []
    for field, value in [("country_code", country), ("status", status), ("event_type", event_type)]:
        if value:
            clauses.append(f"{field}=?")
            args.append(value)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    total = scalar(db, "SELECT COUNT(*) FROM demo_deliveries" + where, tuple(args))
    rows = db.execute(
        "SELECT * FROM demo_deliveries" + where + " ORDER BY sequence DESC LIMIT ? OFFSET ?",
        (*args, limit, offset),
    ).fetchall()
    return {
        "events": [event_view(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def event_detail(db: sqlite3.Connection, delivery_id: str) -> dict:
    row = db.execute("SELECT * FROM demo_deliveries WHERE id=?", (delivery_id,)).fetchone()
    if not row:
        raise DemoError("Event delivery not found in this visitor workspace.", 404)
    related = db.execute(
        "SELECT * FROM demo_deliveries WHERE customer_id=? AND id<>? "
        "ORDER BY sequence DESC LIMIT 12",
        (row["customer_id"], delivery_id),
    ).fetchall()
    lineage = (
        ["sources", "bronze", "contract", "quarantine"]
        if row["status"] in {"quarantined", "replayed"}
        else ["sources", "bronze", "contract", "silver", "portfolio"]
    )
    if row["status"] == "pending":
        lineage = ["sources", "bronze"]
    return {
        "event": event_view(row),
        "raw": json.loads(row["raw"]),
        "issues": json.loads(row["issues"]),
        "lineage": lineage,
        "related": [event_view(item) for item in related],
        "correction": json.loads(row["correction"]) if row["correction"] else None,
        "replayEventId": row["replay_id"],
    }


def analytics(
    db: sqlite3.Connection, country: str | None = None, portfolio_limit: int = 250
) -> dict:
    markets = []
    for item in COUNTRIES:
        code = item["code"]
        if country and country != code:
            continue
        row = db.execute(
            "SELECT * FROM mart_country_performance WHERE country_code=?", (code,)
        ).fetchone()
        money = db.execute(
            "SELECT COUNT(*),COALESCE(SUM(amount),0) FROM mobile_money_transactions "
            "WHERE country_code=? AND currency=?",
            (code, item["currency"]),
        ).fetchone()
        decisions = scalar(
            db,
            "SELECT COUNT(*) FROM mart_application_portfolio "
            "WHERE country_code=? AND decision IS NOT NULL",
            (code,),
        )
        markets.append(
            {
                "countryCode": code,
                "country": item["name"],
                "currency": item["currency"],
                "events": scalar(
                    db, "SELECT COUNT(*) FROM event_fact WHERE country_code=?", (code,)
                ),
                "customers": scalar(
                    db, "SELECT COUNT(*) FROM customers WHERE country_code=?", (code,)
                ),
                "applications": row["applications"] if row else 0,
                "decisions": decisions,
                "approvals": row["approvals"] if row else 0,
                "approvalRate": row["approval_rate_pct"] or 0 if row else 0,
                "par30": row["par30_pct"] if row else None,
                "transactions": money[0],
                "transactionValue": round(money[1], 2),
                "approvedValue": row["approved_value_local"] if row else 0,
                "totalRepaid": round(
                    scalar(
                        db,
                        "SELECT SUM(amount) FROM repayments WHERE country_code=? AND currency=?",
                        (code, item["currency"]),
                    ),
                    2,
                ),
            }
        )
    where, args = (" WHERE country_code=?", (country,)) if country else ("", ())
    types = [
        {"type": row[0], "count": row[1]}
        for row in db.execute(
            "SELECT event_type,COUNT(*) FROM event_fact"
            + where
            + " GROUP BY event_type ORDER BY COUNT(*) DESC",
            args,
        )
    ]
    timeline = [
        {"time": row[0], "count": row[1]}
        for row in db.execute(
            "SELECT substr(occurred_at,1,16)||':00Z',COUNT(*) FROM event_fact"
            + where
            + " GROUP BY substr(occurred_at,1,16) ORDER BY substr(occurred_at,1,16) DESC LIMIT 60",
            args,
        )
    ][::-1]
    portfolio = [
        {
            "applicationId": row["application_id"],
            "customerId": row["customer_id"],
            "countryCode": row["country_code"],
            "currency": row["currency"],
            "requestedAmount": row["requested_amount"],
            "approvedAmount": row["approved_amount"] or 0,
            "totalRepaid": row["total_repaid"],
            "decision": row["decision"] or "pending",
            "score": row["score"],
            "daysPastDue": row["max_days_past_due"],
            "product": row["product_code"],
            "appliedAt": row["applied_at"],
        }
        for row in db.execute(
            "SELECT * FROM mart_application_portfolio"
            + where
            + " ORDER BY applied_at DESC LIMIT ?",
            (*args, portfolio_limit),
        )
    ]
    return {
        "byCountry": markets,
        "byCurrency": [
            {
                key: market[key]
                for key in [
                    "currency",
                    "transactions",
                    "transactionValue",
                    "approvedValue",
                    "totalRepaid",
                ]
            }
            for market in markets
        ],
        "funnel": [
            {"label": "Applications", "value": sum(m["applications"] for m in markets)},
            {"label": "Decisions", "value": sum(m["decisions"] for m in markets)},
            {"label": "Approved in sample", "value": sum(m["approvals"] for m in markets)},
            {
                "label": "With repayment",
                "value": scalar(
                    db,
                    "SELECT COUNT(*) FROM mart_application_portfolio"
                    + (
                        " WHERE country_code=? AND total_repaid>0"
                        if country
                        else " WHERE total_repaid>0"
                    ),
                    args,
                ),
            },
        ],
        "eventTypes": types,
        "timeline": timeline,
        "portfolio": portfolio,
    }


def snapshot(
    db: sqlite3.Connection, country: str | None = None, operation: dict | None = None
) -> dict:
    counts = Counter(
        {
            row[0]: row[1]
            for row in db.execute("SELECT status,COUNT(*) FROM demo_deliveries GROUP BY status")
        }
    )
    accepted = scalar(db, "SELECT COUNT(*) FROM event_fact")
    quarantined_total = counts["quarantined"] + counts["replayed"]
    eligible = accepted + counts["quarantined"]
    page = event_page(db, country)
    runs = [
        json.loads(row[0]) for row in db.execute("SELECT body FROM demo_runs ORDER BY rowid DESC")
    ]
    analyses = analytics(db, country)
    quarantine = []
    for row in db.execute(
        "SELECT * FROM demo_deliveries WHERE status IN ('quarantined','replayed')"
        + (" AND country_code=?" if country else "")
        + " ORDER BY sequence DESC",
        (country,) if country else (),
    ):
        issues = json.loads(row["issues"])
        quarantine.append(
            {
                "id": row["id"],
                "eventId": row["event_id"],
                "eventType": row["event_type"],
                "countryCode": row["country_code"],
                "rule": issues[0]["rule"] if issues else "schema_contract",
                "severity": "error",
                "status": "replayed" if row["status"] == "replayed" else "open",
                "issues": issues,
                "occurredAt": json.loads(row["raw"])["occurred_at"],
                "canReplay": row["status"] == "quarantined" and bool(row["corrected_raw"]),
                "correction": json.loads(row["correction"]) if row["correction"] else None,
            }
        )
    products = []
    for key, name, table, description, columns in [
        (
            "portfolio",
            "Application portfolio",
            "mart_application_portfolio",
            "Latest synthetic decision joined to its application and repayment history.",
            ["application_id", "country_code", "currency", "decision", "total_repaid"],
        ),
        (
            "countries",
            "Country performance",
            "mart_country_performance",
            "Market-level counts and ratios, with monetary values kept in local currency.",
            [
                "country_code",
                "applications",
                "approval_rate_pct",
                "approved_value_local",
                "par30_pct",
            ],
        ),
        (
            "features",
            "Customer features",
            "mart_customer_features",
            "Aggregated synthetic GSM, mobile-money and application observations.",
            [
                "customer_id",
                "country_code",
                "gsm_observations",
                "transaction_count",
                "application_count",
            ],
        ),
        (
            "events",
            "Validated event facts",
            "event_fact",
            "Typed, deduplicated facts using the original FinPulse contract and loader.",
            ["event_id", "event_type", "country_code", "occurred_at", "trace_id"],
        ),
    ]:
        columns = [row[1] for row in db.execute(f'PRAGMA table_info("{table}")')]
        where = " WHERE country_code=?" if country else ""
        args = (country,) if country else ()
        preview = [
            dict(row) for row in db.execute(f"SELECT * FROM {table}" + where + " LIMIT 8", args)
        ]
        export_dataset = {
            "portfolio": "portfolio",
            "countries": "country_performance",
            "features": "features",
            "events": "validated_events",
        }[key]
        products.append(
            {
                "id": key,
                "name": name,
                "tier": "silver" if key == "events" else "gold",
                "rows": scalar(db, f"SELECT COUNT(*) FROM {table}" + where, args),
                "description": description,
                "columns": columns,
                "preview": preview,
                "exportDataset": export_dataset,
                "lineage": ["bronze", "contract", "silver", key],
                "updatedAt": runs[0]["createdAt"] if runs else None,
            }
        )
    return {
        "workspace": {
            "name": "FinPulse sandbox",
            "synthetic": True,
            "revision": meta(db, "revision"),
            "createdAt": meta(db, "createdAt"),
            "selectedCountry": country,
        },
        "stats": {
            "received": sum(counts.values()),
            "accepted": accepted,
            "duplicates": counts["duplicate"],
            "quarantined": quarantined_total,
            "openQuarantine": counts["quarantined"],
            "late": scalar(
                db, "SELECT COUNT(*) FROM demo_deliveries WHERE late=1 AND status='accepted'"
            ),
            "pending": counts["pending"],
            "customers": scalar(db, "SELECT COUNT(*) FROM customers"),
            "qualityScore": round(100 * accepted / eligible, 2) if eligible else 100,
            "countries": scalar(db, "SELECT COUNT(DISTINCT country_code) FROM event_fact"),
            "applications": scalar(db, "SELECT COUNT(*) FROM loan_applications"),
            "transactions": scalar(db, "SELECT COUNT(*) FROM mobile_money_transactions"),
            "lastRunMs": runs[0]["durationMs"] if runs else 0,
        },
        "countries": COUNTRIES,
        "events": page["events"],
        "eventPage": {"shown": len(page["events"]), "total": page["total"], "limit": 250},
        "quarantine": quarantine,
        "runs": runs,
        "analytics": analyses,
        "qualityRules": RULES,
        "products": products,
        "lineage": LINEAGE,
        "audit": [
            json.loads(row[0])
            for row in db.execute("SELECT body FROM demo_audit ORDER BY sequence DESC LIMIT 100")
        ],
        "limits": {"maxEvents": MAX_EVENTS, "maxBatch": MAX_BATCH, "maxRuns": MAX_RUNS},
        "operation": operation,
    }


def export_csv(db: sqlite3.Connection, dataset: str, country: str | None = None) -> str:
    if dataset == "events":
        rows = event_page(db, country, limit=MAX_EVENTS)["events"]
        fields = [
            "id",
            "eventId",
            "eventType",
            "countryCode",
            "currency",
            "amount",
            "occurredAt",
            "status",
            "late",
        ]
    elif dataset in {"portfolio", "features", "validated_events", "country_performance"}:
        table = {
            "portfolio": "mart_application_portfolio",
            "features": "mart_customer_features",
            "validated_events": "event_fact",
            "country_performance": "mart_country_performance",
        }[dataset]
        fields = [row[1] for row in db.execute(f'PRAGMA table_info("{table}")')]
        rows = [
            dict(row)
            for row in db.execute(
                f"SELECT * FROM {table}" + (" WHERE country_code=?" if country else ""),
                (country,) if country else (),
            )
        ]
    elif dataset == "countries":
        rows = analytics(db, country)["byCountry"]
        fields = [
            "countryCode",
            "country",
            "currency",
            "events",
            "applications",
            "approvals",
            "transactionValue",
            "approvedValue",
            "totalRepaid",
        ]
    else:
        raise DemoError(
            "Dataset must be events, validated_events, portfolio, countries, "
            "country_performance or features."
        )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(fields)
    for row in rows:
        values = []
        for field in fields:
            value = str(row.get(field) if row.get(field) is not None else "")
            if value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    audit(
        db,
        "Synthetic CSV exported",
        f"Exported {len(rows)} {dataset} rows with country/currency context "
        "and spreadsheet formula protection.",
    )
    return "\ufeff" + output.getvalue()
