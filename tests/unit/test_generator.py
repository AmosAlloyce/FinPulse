from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from finpulse.contracts import EventType, LoanApplication, LoanDecision, Repayment
from finpulse.generator import SyntheticEventGenerator


def test_generator_is_reproducible() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    first = SyntheticEventGenerator(seed=7, start_time=start)
    second = SyntheticEventGenerator(seed=7, start_time=start)
    assert [event.to_json() for event in first.events(100)] == [
        event.to_json() for event in second.events(100)
    ]


def test_generated_stream_has_referential_coherence() -> None:
    generator = SyntheticEventGenerator(seed=42, start_time=datetime(2026, 1, 1, tzinfo=UTC))
    registered_customers: set[str] = set()
    applications: set[str] = set()
    approved: set[str] = set()

    for event in generator.events(5_000):
        customer_id = str(event.customer_id)
        if event.event_type == EventType.CUSTOMER_REGISTERED:
            registered_customers.add(customer_id)
            continue
        assert customer_id in registered_customers
        if event.event_type == EventType.LOAN_APPLICATION:
            assert isinstance(event.payload, LoanApplication)
            applications.add(str(event.payload.application_id))
        elif event.event_type == EventType.LOAN_DECISION:
            assert isinstance(event.payload, LoanDecision)
            assert str(event.payload.application_id) in applications
            if event.payload.decision == "approved":
                approved.add(str(event.payload.application_id))
        elif event.event_type == EventType.REPAYMENT:
            assert isinstance(event.payload, Repayment)
            assert str(event.payload.application_id) in approved


def test_generator_covers_business_event_types_and_countries() -> None:
    generator = SyntheticEventGenerator(seed=19, start_time=datetime(2026, 1, 1, tzinfo=UTC))
    events = list(generator.events(10_000))
    event_types = Counter(event.event_type for event in events)
    countries = {event.country_code for event in events}
    assert set(event_types) == set(EventType)
    assert countries == {"KEN", "UGA", "GHA", "TZA", "ZMB"}
    assert event_types[EventType.MOBILE_MONEY_TRANSACTION] > 1_000
    assert event_types[EventType.GSM_USAGE] > 1_000


def test_no_raw_phone_number_enters_event_contract() -> None:
    event = SyntheticEventGenerator(
        seed=1, start_time=datetime(2026, 1, 1, tzinfo=UTC)
    ).next_event()
    serialised = event.to_json()
    assert '"phone"' not in serialised
    assert "+254" not in serialised
