from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from finpulse.contracts import EventEnvelope, EventType
from finpulse.generator import SyntheticEventGenerator
from finpulse.quality import QualityIssue, QualityReport, validate_business_rules

LOCAL_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT,
    received INTEGER NOT NULL DEFAULT 0, accepted INTEGER NOT NULL DEFAULT 0,
    quarantined INTEGER NOT NULL DEFAULT 0, duplicates INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS event_fact (
    event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, occurred_at TEXT NOT NULL,
    ingested_at TEXT NOT NULL, source_system TEXT NOT NULL, country_code TEXT NOT NULL,
    customer_id TEXT NOT NULL, correlation_id TEXT NOT NULL, trace_id TEXT NOT NULL,
    payload_json TEXT NOT NULL, processing_date TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_customer_time ON event_fact(customer_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_event_type_time ON event_fact(event_type, occurred_at);
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY, country_code TEXT NOT NULL, registered_at TEXT NOT NULL,
    age_band TEXT NOT NULL, income_band TEXT NOT NULL, occupation TEXT NOT NULL,
    phone_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gsm_usage (
    event_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, occurred_at TEXT NOT NULL,
    country_code TEXT NOT NULL, call_duration_seconds INTEGER NOT NULL,
    sms_count INTEGER NOT NULL, data_mb REAL NOT NULL, unique_contacts INTEGER NOT NULL,
    airtime_topup_amount REAL NOT NULL, network_tenure_days INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS mobile_money_transactions (
    event_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, occurred_at TEXT NOT NULL,
    country_code TEXT NOT NULL, transaction_type TEXT NOT NULL, amount REAL NOT NULL,
    currency TEXT NOT NULL, channel TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS loan_applications (
    application_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, customer_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL, country_code TEXT NOT NULL, requested_amount REAL NOT NULL,
    currency TEXT NOT NULL, term_days INTEGER NOT NULL, product_code TEXT NOT NULL,
    stated_purpose TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS loan_decisions (
    event_id TEXT PRIMARY KEY, application_id TEXT NOT NULL, customer_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL, country_code TEXT NOT NULL, decision TEXT NOT NULL,
    score INTEGER NOT NULL, approved_amount REAL NOT NULL, interest_rate REAL NOT NULL,
    reason_code TEXT NOT NULL, model_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS repayments (
    event_id TEXT PRIMARY KEY, loan_id TEXT NOT NULL, application_id TEXT NOT NULL,
    customer_id TEXT NOT NULL, occurred_at TEXT NOT NULL, country_code TEXT NOT NULL,
    amount REAL NOT NULL, currency TEXT NOT NULL, days_past_due INTEGER NOT NULL,
    payment_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quality_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT, rule TEXT NOT NULL,
    severity TEXT NOT NULL, message TEXT NOT NULL, recorded_at TEXT NOT NULL
);
CREATE VIEW IF NOT EXISTS mart_application_portfolio AS
WITH ranked_decisions AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY application_id ORDER BY occurred_at DESC, event_id DESC
    ) AS row_num
    FROM loan_decisions
), repayment_performance AS (
    SELECT application_id, SUM(amount) AS total_repaid,
           MAX(days_past_due) AS max_days_past_due,
           MAX(CASE WHEN days_past_due > 30 THEN 1 ELSE 0 END) AS ever_par30,
           MAX(CASE WHEN payment_status = 'settled' THEN 1 ELSE 0 END) AS is_settled
    FROM repayments
    GROUP BY application_id
)
SELECT
    a.application_id, a.customer_id, a.occurred_at AS applied_at, a.country_code,
    a.requested_amount, a.currency, a.term_days, a.product_code, a.stated_purpose,
    d.decision, d.score, d.approved_amount, d.interest_rate, d.reason_code, d.model_version,
    COALESCE(r.total_repaid, 0) AS total_repaid,
    COALESCE(r.max_days_past_due, 0) AS max_days_past_due,
    COALESCE(r.ever_par30, 0) AS ever_par30,
    COALESCE(r.is_settled, 0) AS is_settled
FROM loan_applications a
LEFT JOIN ranked_decisions d ON d.application_id = a.application_id AND d.row_num = 1
LEFT JOIN repayment_performance r ON r.application_id = a.application_id;
CREATE VIEW IF NOT EXISTS mart_country_performance AS
SELECT
    country_code,
    COUNT(DISTINCT customer_id) AS applicants,
    COUNT(*) AS applications,
    SUM(CASE WHEN decision = 'approved' THEN 1 ELSE 0 END) AS approvals,
    ROUND(100.0 * SUM(CASE WHEN decision = 'approved' THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN decision IS NOT NULL THEN 1 ELSE 0 END), 0), 2)
        AS approval_rate_pct,
    ROUND(COALESCE(SUM(approved_amount), 0), 2) AS approved_value_local,
    ROUND(AVG(score), 1) AS average_credit_score,
    ROUND(100.0 * AVG(CASE WHEN total_repaid > 0 THEN ever_par30 END), 2) AS par30_pct
FROM mart_application_portfolio
GROUP BY country_code;
CREATE VIEW IF NOT EXISTS mart_credit_funnel AS
SELECT
    (SELECT COUNT(*) FROM loan_applications) AS applications,
    (SELECT COUNT(*) FROM mart_application_portfolio WHERE decision IS NOT NULL) AS decisions,
    (SELECT COUNT(*) FROM mart_application_portfolio WHERE decision = 'approved') AS approvals,
    (SELECT COUNT(DISTINCT application_id) FROM repayments) AS loans_with_repayment,
    (SELECT COUNT(*) FROM repayments WHERE payment_status = 'settled') AS settled_payments;
CREATE VIEW IF NOT EXISTS mart_customer_features AS
WITH gsm AS (
    SELECT customer_id, COUNT(*) AS gsm_observations,
           AVG(unique_contacts) AS avg_unique_contacts,
           SUM(airtime_topup_amount) AS total_airtime_topup
    FROM gsm_usage GROUP BY customer_id
), money AS (
    SELECT customer_id, COUNT(*) AS transaction_count, SUM(amount) AS transaction_value
    FROM mobile_money_transactions GROUP BY customer_id
), credit AS (
    SELECT customer_id, COUNT(*) AS application_count,
           AVG(score) AS avg_credit_score, MAX(max_days_past_due) AS max_days_past_due
    FROM mart_application_portfolio GROUP BY customer_id
)
SELECT
    c.customer_id, c.country_code, c.income_band, c.occupation,
    COALESCE(g.gsm_observations, 0) AS gsm_observations,
    ROUND(COALESCE(g.avg_unique_contacts, 0), 2) AS avg_unique_contacts,
    ROUND(COALESCE(g.total_airtime_topup, 0), 2) AS total_airtime_topup,
    COALESCE(m.transaction_count, 0) AS transaction_count,
    ROUND(COALESCE(m.transaction_value, 0), 2) AS transaction_value,
    COALESCE(cr.application_count, 0) AS application_count,
    ROUND(cr.avg_credit_score, 1) AS avg_credit_score,
    COALESCE(cr.max_days_past_due, 0) AS max_days_past_due
FROM customers c
LEFT JOIN gsm g ON g.customer_id = c.customer_id
LEFT JOIN money m ON m.customer_id = c.customer_id
LEFT JOIN credit cr ON cr.customer_id = c.customer_id;
"""


class LocalPipeline:
    """Portable reference pipeline used by tests and the no-Docker portfolio demo."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.database_path = output_dir / "finpulse.db"
        self.raw_path = output_dir / "bronze" / "events.jsonl"
        self.quarantine_path = output_dir / "quarantine" / "events.jsonl"

    def run(self, raw_records: Iterable[str]) -> dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.raw_path.parent.mkdir(parents=True, exist_ok=True)
        self.quarantine_path.parent.mkdir(parents=True, exist_ok=True)
        if self.database_path.exists():
            self.database_path.unlink()

        report = QualityReport()
        seen: set[str] = set()
        run_id = datetime.now(UTC).strftime("local-%Y%m%dT%H%M%S.%fZ")

        with (
            closing(sqlite3.connect(self.database_path)) as connection,
            self.raw_path.open("w", encoding="utf-8") as raw_file,
            self.quarantine_path.open("w", encoding="utf-8") as quarantine_file,
        ):
            connection.executescript(LOCAL_SCHEMA)
            connection.execute(
                "INSERT INTO pipeline_runs(run_id, started_at) VALUES (?, ?)",
                (run_id, datetime.now(UTC).isoformat()),
            )
            for raw in raw_records:
                report.received += 1
                raw_file.write(raw.rstrip() + "\n")
                try:
                    event = EventEnvelope.from_json(raw)
                except (ValidationError, ValueError) as exc:
                    report.quarantined += 1
                    issue = QualityIssue("schema_contract", "error", str(exc)[:500])
                    report.issues.append(issue)
                    quarantine_file.write(
                        json.dumps({"raw": raw, "reason": "schema_contract", "error": str(exc)})
                        + "\n"
                    )
                    continue

                event_id = str(event.event_id)
                if event_id in seen:
                    report.duplicates += 1
                    continue
                seen.add(event_id)

                issues = validate_business_rules(
                    event, now=max(datetime.now(UTC), event.ingested_at)
                )
                error_issues = [issue for issue in issues if issue.severity == "error"]
                report.issues.extend(issues)
                if error_issues:
                    report.quarantined += 1
                    quarantine_file.write(
                        json.dumps(
                            {
                                "raw": raw,
                                "reason": "business_rule",
                                "errors": [issue.message for issue in error_issues],
                            }
                        )
                        + "\n"
                    )
                    continue
                if any(issue.rule == "freshness_24h" for issue in issues):
                    report.late_events += 1

                self._load_event(connection, event)
                report.accepted += 1

            self._record_issues(connection, report.issues)
            connection.execute(
                """UPDATE pipeline_runs SET completed_at = ?, received = ?, accepted = ?,
                   quarantined = ?, duplicates = ? WHERE run_id = ?""",
                (
                    datetime.now(UTC).isoformat(),
                    report.received,
                    report.accepted,
                    report.quarantined,
                    report.duplicates,
                    run_id,
                ),
            )
            connection.commit()
            summary = self._summary(connection, run_id, report)

        (self.output_dir / "quality-report.json").write_text(
            json.dumps(report.as_dict(), indent=2), encoding="utf-8"
        )
        (self.output_dir / "demo-summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        self._write_lineage_manifest(summary)
        return summary

    def _load_event(self, connection: sqlite3.Connection, event: EventEnvelope) -> None:
        payload = event.payload.model_dump(mode="json")
        common = (
            str(event.event_id),
            event.event_type.value,
            event.occurred_at.isoformat(),
            event.ingested_at.isoformat(),
            event.source_system,
            event.country_code,
            str(event.customer_id),
            str(event.correlation_id),
            event.trace_id,
            json.dumps(payload, separators=(",", ":")),
            event.occurred_at.date().isoformat(),
        )
        connection.execute(
            "INSERT INTO event_fact VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", common
        )
        event_id = str(event.event_id)
        customer_id = str(event.customer_id)
        occurred_at = event.occurred_at.isoformat()
        country = event.country_code

        if event.event_type == EventType.CUSTOMER_REGISTERED:
            connection.execute(
                "INSERT OR IGNORE INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    customer_id,
                    country,
                    occurred_at,
                    payload["age_band"],
                    payload["income_band"],
                    payload["occupation"],
                    payload["phone_hash"],
                ),
            )
        elif event.event_type == EventType.GSM_USAGE:
            connection.execute(
                "INSERT INTO gsm_usage VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    customer_id,
                    occurred_at,
                    country,
                    payload["call_duration_seconds"],
                    payload["sms_count"],
                    payload["data_mb"],
                    payload["unique_contacts"],
                    payload["airtime_topup_amount"],
                    payload["network_tenure_days"],
                ),
            )
        elif event.event_type == EventType.MOBILE_MONEY_TRANSACTION:
            connection.execute(
                "INSERT INTO mobile_money_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    customer_id,
                    occurred_at,
                    country,
                    payload["transaction_type"],
                    payload["amount"],
                    payload["currency"],
                    payload["channel"],
                ),
            )
        elif event.event_type == EventType.LOAN_APPLICATION:
            connection.execute(
                "INSERT OR IGNORE INTO loan_applications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    payload["application_id"],
                    event_id,
                    customer_id,
                    occurred_at,
                    country,
                    payload["requested_amount"],
                    payload["currency"],
                    payload["term_days"],
                    payload["product_code"],
                    payload["stated_purpose"],
                ),
            )
        elif event.event_type == EventType.LOAN_DECISION:
            connection.execute(
                "INSERT INTO loan_decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    payload["application_id"],
                    customer_id,
                    occurred_at,
                    country,
                    payload["decision"],
                    payload["score"],
                    payload["approved_amount"],
                    payload["interest_rate"],
                    payload["reason_code"],
                    payload["model_version"],
                ),
            )
        elif event.event_type == EventType.REPAYMENT:
            connection.execute(
                "INSERT INTO repayments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    payload["loan_id"],
                    payload["application_id"],
                    customer_id,
                    occurred_at,
                    country,
                    payload["amount"],
                    payload["currency"],
                    payload["days_past_due"],
                    payload["payment_status"],
                ),
            )

    @staticmethod
    def _record_issues(connection: sqlite3.Connection, issues: list[QualityIssue]) -> None:
        connection.executemany(
            """INSERT INTO quality_issues(event_id, rule, severity, message, recorded_at)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (
                    issue.event_id,
                    issue.rule,
                    issue.severity,
                    issue.message,
                    datetime.now(UTC).isoformat(),
                )
                for issue in issues
            ],
        )

    @staticmethod
    def _summary(
        connection: sqlite3.Connection, run_id: str, report: QualityReport
    ) -> dict[str, Any]:
        def scalar(query: str) -> int | float:
            value = connection.execute(query).fetchone()[0]
            return value or 0

        cursor = connection.execute("SELECT * FROM mart_country_performance ORDER BY country_code")
        columns = [column[0] for column in cursor.description]
        countries = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        applications = int(scalar("SELECT COUNT(*) FROM mart_application_portfolio"))
        approvals = int(
            scalar("SELECT COUNT(*) FROM mart_application_portfolio WHERE decision = 'approved'")
        )
        decisions = int(
            scalar("SELECT COUNT(*) FROM mart_application_portfolio WHERE decision IS NOT NULL")
        )
        return {
            "run_id": run_id,
            "status": "success",
            "records": report.as_dict(),
            "business_metrics": {
                "customers": int(scalar("SELECT COUNT(*) FROM customers")),
                "applicants": int(
                    scalar("SELECT COUNT(DISTINCT customer_id) FROM loan_applications")
                ),
                "applications": applications,
                "decisions": decisions,
                "approvals": approvals,
                "loans_with_repayment": int(
                    scalar(
                        """SELECT COUNT(*) FROM mart_application_portfolio
                           WHERE total_repaid > 0"""
                    )
                ),
                "approval_rate_pct": round(100 * approvals / decisions, 2) if decisions else 0,
                "transactions": int(scalar("SELECT COUNT(*) FROM mobile_money_transactions")),
                "repayments": int(scalar("SELECT COUNT(*) FROM repayments")),
                "par30_pct": round(
                    float(
                        scalar(
                            """SELECT 100.0 * AVG(ever_par30)
                               FROM mart_application_portfolio
                               WHERE total_repaid > 0"""
                        )
                    ),
                    2,
                ),
            },
            "country_performance": countries,
            "artifacts": {
                "sqlite_warehouse": "finpulse.db",
                "bronze_events": "bronze/events.jsonl",
                "quarantine": "quarantine/events.jsonl",
                "quality_report": "quality-report.json",
            },
        }

    def _write_lineage_manifest(self, summary: dict[str, Any]) -> None:
        manifest = {
            "platform": "FinPulse",
            "run_id": summary["run_id"],
            "generated_at": datetime.now(UTC).isoformat(),
            "nodes": [
                {"id": "synthetic_sources", "type": "source"},
                {"id": "bronze_events", "type": "dataset"},
                {"id": "contract_quality_gate", "type": "transformation"},
                {"id": "silver_event_facts", "type": "dataset"},
                {"id": "warehouse_marts", "type": "dataset"},
            ],
            "edges": [
                ["synthetic_sources", "bronze_events"],
                ["bronze_events", "contract_quality_gate"],
                ["contract_quality_gate", "silver_event_facts"],
                ["silver_event_facts", "warehouse_marts"],
            ],
        }
        (self.output_dir / "lineage.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )


def run_local_demo(event_count: int, output_dir: Path, seed: int = 42) -> dict[str, Any]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    generator = SyntheticEventGenerator(seed=seed, start_time=datetime(2026, 1, 1, tzinfo=UTC))
    records = [event.to_json() for event in generator.events(event_count)]

    # Exercise exactly-once deduplication and quarantine without overwhelming the demo dataset.
    if len(records) >= 100:
        records.extend(records[index] for index in range(0, len(records), 251))
        records.extend(
            [
                '{"schema_version":"0.0","malformed":true}',
                '{"event_id":"not-a-uuid","event_type":"repayment"}',
            ]
        )
    return LocalPipeline(output_dir).run(records)
