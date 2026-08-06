from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from finpulse.local_pipeline import run_local_demo


def test_local_demo_builds_a_queryable_data_product(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    summary = run_local_demo(2_000, output, seed=42)

    assert summary["status"] == "success"
    assert summary["records"]["accepted"] == 2_000
    assert summary["records"]["duplicates"] > 0
    assert summary["records"]["quarantined"] == 2
    assert summary["business_metrics"]["customers"] >= 25
    assert summary["business_metrics"]["applications"] > 0
    assert summary["business_metrics"]["transactions"] > 0
    assert (
        sum(row["applications"] for row in summary["country_performance"])
        == summary["business_metrics"]["applications"]
    )

    for artifact in [
        "finpulse.db",
        "bronze/events.jsonl",
        "quarantine/events.jsonl",
        "quality-report.json",
        "demo-summary.json",
        "lineage.json",
    ]:
        assert (output / artifact).exists()

    with closing(sqlite3.connect(output / "finpulse.db")) as connection:
        country_rows = connection.execute(
            "SELECT COUNT(*) FROM mart_country_performance"
        ).fetchone()[0]
        feature_rows = connection.execute("SELECT COUNT(*) FROM mart_customer_features").fetchone()[
            0
        ]
        event_rows = connection.execute("SELECT COUNT(*) FROM event_fact").fetchone()[0]
    assert country_rows == 5
    assert feature_rows == summary["business_metrics"]["customers"]
    assert event_rows == 2_000


def test_quality_report_is_machine_readable(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    run_local_demo(200, output, seed=9)
    report = json.loads((output / "quality-report.json").read_text())
    assert report["status"] == "pass"
    assert report["acceptance_rate"] > 0.98
    assert report["issue_counts"]["schema_contract"] == 2
