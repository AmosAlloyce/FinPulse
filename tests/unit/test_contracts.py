from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from finpulse.contracts import EventEnvelope, EventType, GsmUsage, stable_hash


def make_event() -> EventEnvelope:
    return EventEnvelope(
        event_type=EventType.GSM_USAGE,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        ingested_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
        source_system="gsm",
        country_code="KEN",
        customer_id=uuid4(),
        payload=GsmUsage(
            call_duration_seconds=120,
            sms_count=3,
            data_mb=55.5,
            unique_contacts=8,
            airtime_topup_amount=10,
            network_tenure_days=500,
        ),
    )


def test_event_round_trip_preserves_contract() -> None:
    event = make_event()
    restored = EventEnvelope.from_json(event.to_json())
    assert restored == event
    assert restored.occurred_at.tzinfo is not None


def test_payload_type_must_match_envelope() -> None:
    data = make_event().model_dump()
    data["event_type"] = EventType.REPAYMENT
    with pytest.raises(ValidationError, match="must match"):
        EventEnvelope.model_validate(data)


def test_naive_timestamps_are_rejected() -> None:
    data = make_event().model_dump()
    data["occurred_at"] = datetime(2026, 1, 1)
    with pytest.raises(ValidationError, match="timezone"):
        EventEnvelope.model_validate(data)


def test_hash_is_stable_and_does_not_expose_input() -> None:
    first = stable_hash("+254700000000")
    second = stable_hash("+254700000000")
    assert first == second
    assert len(first) == 64
    assert "+254" not in first


def test_payload_rejects_impossible_values() -> None:
    with pytest.raises(ValidationError):
        GsmUsage(
            call_duration_seconds=-1,
            sms_count=0,
            data_mb=0,
            unique_contacts=0,
            airtime_topup_amount=0,
            network_tenure_days=0,
        )
