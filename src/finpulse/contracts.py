from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


class EventType(StrEnum):
    CUSTOMER_REGISTERED = "customer_registered"
    GSM_USAGE = "gsm_usage"
    MOBILE_MONEY_TRANSACTION = "mobile_money_transaction"
    DEVICE_SIGNAL = "device_signal"
    LOAN_APPLICATION = "loan_application"
    LOAN_DECISION = "loan_decision"
    REPAYMENT = "repayment"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CustomerRegistered(StrictModel):
    event_type: Literal[EventType.CUSTOMER_REGISTERED] = EventType.CUSTOMER_REGISTERED
    phone_hash: str = Field(min_length=64, max_length=64)
    age_band: Literal["18-24", "25-34", "35-44", "45-54", "55+"]
    income_band: Literal["low", "lower_middle", "upper_middle", "high"]
    occupation: Literal["farmer", "merchant", "salaried", "gig_worker", "other"]
    consent_version: str = "v2.1"


class GsmUsage(StrictModel):
    event_type: Literal[EventType.GSM_USAGE] = EventType.GSM_USAGE
    call_duration_seconds: int = Field(ge=0, le=14_400)
    sms_count: int = Field(ge=0, le=1_000)
    data_mb: float = Field(ge=0, le=100_000)
    unique_contacts: int = Field(ge=0, le=5_000)
    airtime_topup_amount: float = Field(ge=0)
    network_tenure_days: int = Field(ge=0)


class MobileMoneyTransaction(StrictModel):
    event_type: Literal[EventType.MOBILE_MONEY_TRANSACTION] = EventType.MOBILE_MONEY_TRANSACTION
    transaction_type: Literal["cash_in", "cash_out", "p2p", "merchant_pay", "bill_pay"]
    amount: float = Field(gt=0, le=1_000_000)
    currency: Literal["KES", "UGX", "GHS", "TZS", "ZMW"]
    counterparty_hash: str = Field(min_length=16, max_length=64)
    channel: Literal["ussd", "app", "agent"]


class DeviceSignal(StrictModel):
    event_type: Literal[EventType.DEVICE_SIGNAL] = EventType.DEVICE_SIGNAL
    device_hash: str = Field(min_length=16, max_length=64)
    sim_slot_count: int = Field(ge=1, le=4)
    device_age_months: int = Field(ge=0, le=240)
    is_rooted: bool
    location_cell_changes_24h: int = Field(ge=0, le=10_000)


class LoanApplication(StrictModel):
    event_type: Literal[EventType.LOAN_APPLICATION] = EventType.LOAN_APPLICATION
    application_id: UUID
    requested_amount: float = Field(gt=0, le=1_000_000)
    currency: Literal["KES", "UGX", "GHS", "TZS", "ZMW"]
    term_days: Literal[7, 14, 30, 60, 90]
    product_code: Literal["nano", "working_capital", "personal"]
    stated_purpose: Literal["inventory", "emergency", "education", "agriculture", "other"]


class LoanDecision(StrictModel):
    event_type: Literal[EventType.LOAN_DECISION] = EventType.LOAN_DECISION
    application_id: UUID
    decision: Literal["approved", "declined", "manual_review"]
    score: int = Field(ge=0, le=1_000)
    approved_amount: float = Field(ge=0, le=1_000_000)
    interest_rate: float = Field(ge=0, le=1)
    reason_code: Literal[
        "affordability_pass",
        "thin_file",
        "velocity_risk",
        "affordability_fail",
        "policy_limit",
    ]
    model_version: str = "credit-risk-2026.08"


class Repayment(StrictModel):
    event_type: Literal[EventType.REPAYMENT] = EventType.REPAYMENT
    loan_id: UUID
    application_id: UUID
    amount: float = Field(gt=0, le=1_000_000)
    currency: Literal["KES", "UGX", "GHS", "TZS", "ZMW"]
    days_past_due: int = Field(ge=0, le=3_650)
    payment_status: Literal["on_time", "late", "partial", "settled"]


EventPayload = Annotated[
    CustomerRegistered
    | GsmUsage
    | MobileMoneyTransaction
    | DeviceSignal
    | LoanApplication
    | LoanDecision
    | Repayment,
    Field(discriminator="event_type"),
]
payload_adapter: TypeAdapter[EventPayload] = TypeAdapter(EventPayload)


class EventEnvelope(BaseModel):
    """Versioned, traceable contract for every event entering the platform."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    schema_version: Literal["1.0"] = "1.0"
    event_type: EventType
    occurred_at: datetime
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_system: Literal["gsm", "mobile_money", "credit_engine", "loan_ledger", "identity"]
    country_code: Literal["KEN", "UGA", "GHA", "TZA", "ZMB"]
    customer_id: UUID
    correlation_id: UUID = Field(default_factory=uuid4)
    trace_id: str = Field(default_factory=lambda: uuid4().hex)
    payload: EventPayload

    @field_validator("occurred_at", "ingested_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def payload_matches_envelope(self) -> EventEnvelope:
        if self.payload.event_type != self.event_type:
            raise ValueError("envelope event_type must match payload event_type")
        return self

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, value: str | bytes) -> EventEnvelope:
        return cls.model_validate_json(value)


def stable_hash(value: str, salt: str = "finpulse-demo") -> str:
    """Pseudonymise identifiers before they enter analytics storage."""

    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()


def json_schema() -> dict[str, Any]:
    """Expose the event schema for contract checks and documentation."""

    return EventEnvelope.model_json_schema()
