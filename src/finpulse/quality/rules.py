from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from finpulse.contracts import EventEnvelope, EventType, LoanDecision, Repayment


@dataclass(frozen=True)
class QualityIssue:
    rule: str
    severity: str
    message: str
    event_id: str | None = None


@dataclass
class QualityReport:
    received: int = 0
    accepted: int = 0
    duplicates: int = 0
    quarantined: int = 0
    late_events: int = 0
    issues: list[QualityIssue] = field(default_factory=list)

    @property
    def acceptance_rate(self) -> float:
        # Duplicates are a delivery characteristic, not bad data. Track them separately.
        quality_eligible = self.received - self.duplicates
        return self.accepted / quality_eligible if quality_eligible else 1.0

    def as_dict(self) -> dict[str, Any]:
        issue_counts = Counter(issue.rule for issue in self.issues)
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "received": self.received,
            "accepted": self.accepted,
            "duplicates": self.duplicates,
            "quarantined": self.quarantined,
            "late_events": self.late_events,
            "acceptance_rate": round(self.acceptance_rate, 6),
            "issue_counts": dict(issue_counts),
            "status": "pass" if self.acceptance_rate >= 0.99 else "warn",
            "issues": [asdict(issue) for issue in self.issues[:100]],
        }


def validate_business_rules(
    event: EventEnvelope, now: datetime | None = None
) -> list[QualityIssue]:
    """Rules that go beyond structural schema validation."""

    issues: list[QualityIssue] = []
    event_id = str(event.event_id)
    reference_time = now or datetime.now(UTC)

    if event.occurred_at > reference_time + timedelta(minutes=5):
        issues.append(
            QualityIssue("event_not_in_future", "error", "occurred_at is in the future", event_id)
        )
    if event.ingested_at < event.occurred_at:
        issues.append(
            QualityIssue(
                "ingestion_after_occurrence",
                "error",
                "ingested_at precedes occurred_at",
                event_id,
            )
        )
    if event.ingested_at - event.occurred_at > timedelta(hours=24):
        issues.append(
            QualityIssue("freshness_24h", "warning", "event arrived more than 24h late", event_id)
        )
    if event.event_type == EventType.LOAN_DECISION:
        payload = event.payload
        assert isinstance(payload, LoanDecision)
        if payload.decision != "approved" and payload.approved_amount != 0:
            issues.append(
                QualityIssue(
                    "declined_amount_zero",
                    "error",
                    "non-approved decision has an approved amount",
                    event_id,
                )
            )
    if event.event_type == EventType.REPAYMENT:
        payload = event.payload
        assert isinstance(payload, Repayment)
        if payload.days_past_due == 0 and payload.payment_status in {"late", "partial"}:
            issues.append(
                QualityIssue(
                    "repayment_status_consistency",
                    "error",
                    "late/partial payment must have positive days past due",
                    event_id,
                )
            )
    return issues
