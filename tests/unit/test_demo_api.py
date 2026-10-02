from __future__ import annotations

import csv
import io
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finpulse.demo.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(tmp_path / "data", public_origin="https://testserver", cookie_path="/")
    with TestClient(app, base_url="https://testserver") as browser:
        yield browser


def test_seed_executes_original_engine_and_has_correct_delivery_accounting(client):
    response = client.get("/api/workspace")
    assert response.status_code == 200
    result = response.json()
    stats = result["stats"]
    assert stats["received"] == 980
    assert stats["accepted"] == 966
    assert stats["duplicates"] == 8
    assert stats["openQuarantine"] == 6
    assert stats["late"] == 6
    assert stats["pending"] == 0
    assert stats["countries"] == 5
    assert sum(row["events"] for row in result["analytics"]["byCountry"]) == 966
    assert len(result["runs"]) == 2
    assert len(result["events"]) == 250
    assert all(len(run["steps"]) == 5 for run in result["runs"])
    assert {rule["id"] for rule in result["qualityRules"]} >= {
        "schema_contract",
        "freshness_24h",
        "repayment_status_consistency",
    }
    cookie = response.headers["set-cookie"]
    assert all(attribute in cookie for attribute in ["Secure", "HttpOnly", "SameSite=lax"])


def test_simulation_is_staged_and_duplicates_never_inflate_facts(client):
    before = client.get("/api/workspace").json()
    staged = client.post("/api/simulate", json={"scenario": "duplicates", "count": 12}).json()
    assert staged["stats"]["pending"] == 12
    assert staged["stats"]["accepted"] == before["stats"]["accepted"]
    run = client.post("/api/pipeline/run", json={}).json()
    assert run["operation"]["counts"]["duplicates"] == 12
    assert run["operation"]["counts"]["accepted"] == 0
    assert run["stats"]["accepted"] == before["stats"]["accepted"]
    assert run["analytics"]["byCurrency"] == before["analytics"]["byCurrency"]
    assert client.post("/api/pipeline/run", json={}).status_code == 409


def test_real_quality_rules_quarantine_invalid_and_accept_late_with_warning(client):
    before = client.get("/api/workspace").json()["stats"]
    client.post("/api/simulate", json={"scenario": "invalid", "count": 3})
    result = client.post("/api/pipeline/run", json={}).json()
    assert result["operation"]["counts"]["quarantined"] == 3
    assert result["stats"]["accepted"] == before["accepted"]
    assert {item["rule"] for item in result["quarantine"]} >= {
        "schema_contract",
        "ingestion_after_occurrence",
        "event_not_in_future",
    }
    client.post("/api/simulate", json={"scenario": "late", "count": 4})
    late = client.post("/api/pipeline/run", json={}).json()
    assert late["operation"]["counts"]["accepted"] == 4
    assert late["operation"]["counts"]["late"] == 4
    assert late["stats"]["late"] == before["late"] + 4
    assert late["stats"]["openQuarantine"] == before["openQuarantine"] + 3


def test_replay_requires_explicit_approval_preserves_raw_and_is_idempotent(client):
    initial = client.get("/api/workspace").json()
    item = initial["quarantine"][0]
    original = client.get(f"/api/events/{item['id']}").json()
    assert client.post(f"/api/quarantine/{item['id']}/replay", json={}).status_code == 400
    assert (
        client.post(
            f"/api/quarantine/{item['id']}/replay", json={"decision": "approve", "raw": {}}
        ).status_code
        == 400
    )
    approved = client.post(
        f"/api/quarantine/{item['id']}/replay", json={"decision": "approve"}
    ).json()
    assert approved["stats"]["accepted"] == initial["stats"]["accepted"] + 1
    assert approved["stats"]["openQuarantine"] == initial["stats"]["openQuarantine"] - 1
    assert any(event["action"] == "Known correction approved" for event in approved["audit"])
    after = client.get(f"/api/events/{item['id']}").json()
    assert after["raw"] == original["raw"]
    assert after["event"]["status"] == "replayed"
    corrected = client.get(f"/api/events/{after['replayEventId']}").json()
    assert corrected["event"]["status"] == "accepted"
    assert corrected["event"]["eventId"] == original["event"]["eventId"]
    assert (
        client.post(
            f"/api/quarantine/{item['id']}/replay", json={"decision": "approve"}
        ).status_code
        == 409
    )
    assert client.get("/api/workspace").json()["stats"]["accepted"] == approved["stats"]["accepted"]


def test_country_filters_and_exports_never_mix_currency_amounts(client):
    workspace = client.get("/api/workspace").json()
    currency_rows = workspace["analytics"]["byCurrency"]
    assert {row["currency"] for row in currency_rows} == {"KES", "UGX", "GHS", "TZS", "ZMW"}
    assert "transactionValue" not in workspace["stats"]
    selected = client.get("/api/workspace?country=KEN").json()
    assert selected["stats"] == workspace["stats"]
    assert len(selected["analytics"]["byCountry"]) == 1
    assert all(event["countryCode"] == "KEN" for event in selected["events"])
    assert all(row["currency"] == "KES" for row in selected["analytics"]["byCurrency"])
    response = client.get("/api/export?dataset=countries")
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
    assert len(rows) == 5
    assert {row["currency"] for row in rows} == {"KES", "UGX", "GHS", "TZS", "ZMW"}
    assert client.get("/api/export?dataset=raw_sql").status_code == 400


def test_product_previews_and_exports_use_the_actual_complete_sql_datasets(client):
    workspace = client.get("/api/workspace").json()
    for product in workspace["products"]:
        assert len(product["preview"]) <= 8
        assert list(product["preview"][0]) == product["columns"]
        response = client.get("/api/export", params={"dataset": product["exportDataset"]})
        assert response.status_code == 200
        reader = csv.DictReader(io.StringIO(response.text.lstrip("\ufeff")))
        assert reader.fieldnames == product["columns"]
        assert len(list(reader)) == product["rows"]
    accepted = client.get("/api/export?dataset=validated_events")
    deliveries = client.get("/api/export?dataset=events")
    assert len(list(csv.DictReader(io.StringIO(accepted.text.lstrip("\ufeff"))))) == 966
    assert len(list(csv.DictReader(io.StringIO(deliveries.text.lstrip("\ufeff"))))) == 980


def test_event_pagination_lineage_and_mutation_input_boundaries(client):
    page = client.get("/api/events?limit=7&offset=7&status=accepted&type=gsm_usage").json()
    assert len(page["events"]) == 7
    assert all(
        row["eventType"] == "gsm_usage" and row["status"] == "accepted" for row in page["events"]
    )
    detail = client.get(f"/api/events/{page['events'][0]['id']}").json()
    assert detail["raw"]["trace_id"]
    assert "silver" in detail["lineage"]
    assert len(detail["related"]) <= 12
    for body in [
        {"scenario": [], "count": 2},
        {"scenario": "normal", "count": True},
        {"scenario": "normal", "count": 101},
        {"scenario": "normal", "count": 2, "raw": {}},
    ]:
        assert client.post("/api/simulate", json=body).status_code == 400
    assert client.get("/api/events?offset=-1").status_code == 400
    assert client.get("/api/workspace?country=USA").status_code == 400
    assert client.post("/api/query", json={"sql": "DELETE FROM event_fact"}).status_code == 404
    assert (
        client.post("/api/reset", json={}, headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert (
        client.post("/api/reset", content="{}", headers={"Content-Type": "text/plain"}).status_code
        == 415
    )
    assert client.post("/api/simulate", json={"scenario": "x" * 9000}).status_code == 413


def test_workspace_isolation_reset_and_restart_persistence(tmp_path):
    directory = tmp_path / "persisted"
    app = create_app(directory, public_origin="https://testserver", cookie_path="/")
    with TestClient(app, base_url="https://testserver") as first:
        before = first.get("/api/workspace").json()
        item = before["quarantine"][0]
        saved_cookie = first.cookies.get("finpulse_session")
        second_cookie = None
        with TestClient(app, base_url="https://testserver") as second:
            other = second.get("/api/workspace").json()
            second_cookie = second.cookies.get("finpulse_session")
            assert second.get(f"/api/events/{item['id']}").status_code == 404
            assert (
                second.post(
                    f"/api/quarantine/{item['id']}/replay", json={"decision": "approve"}
                ).status_code
                == 404
            )
            approved = first.post(
                f"/api/quarantine/{item['id']}/replay", json={"decision": "approve"}
            ).json()
            assert second.get("/api/workspace").json()["stats"] == other["stats"]
        # The shared TestClient lifespan closes the index; no more calls on this app.
    restarted = create_app(directory, public_origin="https://testserver", cookie_path="/")
    with TestClient(restarted, base_url="https://testserver") as visitor:
        visitor.cookies.set("finpulse_session", saved_cookie)
        assert (
            visitor.get("/api/workspace").json()["stats"]["accepted"]
            == approved["stats"]["accepted"]
        )
        reset = visitor.post("/api/reset", json={})
        assert reset.status_code == 200
        assert reset.json()["stats"]["accepted"] == before["stats"]["accepted"]
        visitor.cookies.clear()
        visitor.cookies.set("finpulse_session", second_cookie)
        assert (
            visitor.get("/api/workspace").json()["stats"]["accepted"] == before["stats"]["accepted"]
        )


def test_capacity_and_expiry_are_bounded(tmp_path):
    app = create_app(
        tmp_path / "limited",
        public_origin="https://testserver",
        cookie_path="/",
        max_sessions=1,
        ttl=1,
    )
    with TestClient(app, base_url="https://testserver") as first:
        assert first.get("/api/workspace").status_code == 200
        first.cookies.clear()
        assert first.get("/api/workspace").status_code == 503
        time.sleep(1.05)
        assert first.get("/api/workspace").status_code == 200
        assert len(list((tmp_path / "limited").glob("*.sqlite"))) == 2


def test_storage_operation_rolls_back_when_pipeline_fails(client):
    client.get("/api/workspace")
    sid = client.cookies.get("finpulse_session")
    store = client.app.state.store
    with pytest.raises(RuntimeError), store.workspace(sid) as db:
        db.execute("DELETE FROM event_fact")
        raise RuntimeError("simulated failed publication")
    assert client.get("/api/workspace").json()["stats"]["accepted"] == 966


def test_static_deep_links_and_missing_api_are_distinct(tmp_path):
    frontend = tmp_path / "web"
    frontend.mkdir()
    (frontend / "index.html").write_text('<html><div id="root"></div></html>')
    app = create_app(tmp_path / "data", cookie_path="/", web_dist=frontend)
    with TestClient(app) as browser:
        assert browser.get("/markets").status_code == 200
        assert browser.get("/missing.js").status_code == 404
        assert browser.get("/api/not-found").status_code == 404


def test_delivery_limit_reserves_room_for_known_corrections(client):
    client.get("/api/workspace")
    for _ in range(15):
        response = client.post("/api/simulate", json={"scenario": "duplicates", "count": 100})
        assert response.status_code == 200
    # 2,480 deliveries plus six existing corrections leaves room for seven new
    # invalid deliveries and their seven future replays, but not eight.
    assert client.post("/api/simulate", json={"scenario": "invalid", "count": 8}).status_code == 429
    allowed = client.post("/api/simulate", json={"scenario": "invalid", "count": 7})
    assert allowed.status_code == 200
    assert allowed.json()["stats"]["received"] == 2487
    assert client.post("/api/simulate", json={"scenario": "normal", "count": 1}).status_code == 429
