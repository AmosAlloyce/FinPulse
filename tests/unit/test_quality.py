from __future__ import annotations

from datetime import UTC, datetime, timedelta

from finpulse.contracts import EventType, Repayment
from finpulse.generator import SyntheticEventGenerator
from finpulse.quality import validate_business_rules


def test_ingestion_must_follow_occurrence() -> None:
    event = SyntheticEventGenerator(start_time=datetime(2026, 1, 1, tzinfo=UTC)).next_event()
    invalid = event.model_copy(update={"ingested_at": event.occurred_at - timedelta(seconds=1)})
    rules = {issue.rule for issue in validate_business_rules(invalid, now=event.occurred_at)}
    assert "ingestion_after_occurrence" in rules


def test_late_event_is_warning_not_error() -> None:
    event = SyntheticEventGenerator(start_time=datetime(2026, 1, 1, tzinfo=UTC)).next_event()
    late = event.model_copy(update={"ingested_at": event.occurred_at + timedelta(days=2)})
    issues = validate_business_rules(late, now=late.ingested_at)
    assert any(issue.rule == "freshness_24h" and issue.severity == "warning" for issue in issues)


def test_inconsistent_repayment_is_rejected() -> None:
    generator = SyntheticEventGenerator(start_time=datetime(2026, 1, 1, tzinfo=UTC))
    base = generator.next_event()
    payload = Repayment(
        loan_id=base.event_id,
        application_id=base.event_id,
        amount=10,
        currency="KES",
        days_past_due=0,
        payment_status="late",
    )
    repayment = base.model_copy(update={"event_type": EventType.REPAYMENT, "payload": payload})
    issues = validate_business_rules(repayment, now=repayment.ingested_at)
    assert any(issue.rule == "repayment_status_consistency" for issue in issues)
