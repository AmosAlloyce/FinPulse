from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid5

from finpulse.contracts import (
    CustomerRegistered,
    DeviceSignal,
    EventEnvelope,
    EventPayload,
    GsmUsage,
    LoanApplication,
    LoanDecision,
    MobileMoneyTransaction,
    Repayment,
    stable_hash,
)

NAMESPACE = UUID("aa7eae6b-f756-4218-bbc9-c76b7bc9f02f")
CURRENCIES = {"KEN": "KES", "UGA": "UGX", "GHA": "GHS", "TZA": "TZS", "ZMB": "ZMW"}
AMOUNT_SCALE = {"KES": 1.0, "UGX": 25.0, "GHS": 0.08, "TZS": 17.0, "ZMW": 0.15}


@dataclass
class CustomerState:
    customer_id: UUID
    country: str
    phone_hash: str
    risk_tier: float
    income_band: str
    network_tenure_days: int
    applications: list[UUID] = field(default_factory=list)
    approved_applications: list[UUID] = field(default_factory=list)


class SyntheticEventGenerator:
    """Stateful generator that creates coherent, reproducible fintech event streams."""

    def __init__(
        self,
        seed: int = 42,
        countries: list[str] | None = None,
        start_time: datetime | None = None,
    ) -> None:
        self.random = random.Random(seed)
        self.seed = seed
        self.countries = countries or ["KEN", "UGA", "GHA", "TZA", "ZMB"]
        self.clock = start_time or datetime.now(UTC)
        self.customers: list[CustomerState] = []
        self.sequence = 0

    def events(self, count: int) -> Iterator[EventEnvelope]:
        for _ in range(count):
            yield self.next_event()

    def next_event(self) -> EventEnvelope:
        self.sequence += 1
        self.clock += timedelta(milliseconds=self.random.randint(100, 4_000))

        if len(self.customers) < 25 or self.random.random() < 0.025:
            return self._register_customer()

        customer = self.random.choice(self.customers)
        choices = ["gsm", "money", "device", "application"]
        weights = [0.38, 0.35, 0.08, 0.13]
        if customer.approved_applications:
            choices.append("repayment")
            weights.append(0.06)
        event_kind = self.random.choices(choices, weights=weights, k=1)[0]

        if event_kind == "gsm":
            return self._gsm_event(customer)
        if event_kind == "money":
            return self._money_event(customer)
        if event_kind == "device":
            return self._device_event(customer)
        if event_kind == "repayment":
            return self._repayment_event(customer)
        return self._application_or_decision(customer)

    def _envelope(
        self,
        customer: CustomerState,
        payload: EventPayload,
        source: Literal["gsm", "mobile_money", "credit_engine", "loan_ledger", "identity"],
    ) -> EventEnvelope:
        event_type = payload.event_type
        event_uuid = uuid5(NAMESPACE, f"{self.seed}:{self.sequence}:{event_type}")
        return EventEnvelope(
            event_id=event_uuid,
            event_type=event_type,
            occurred_at=self.clock,
            ingested_at=self.clock + timedelta(milliseconds=self.random.randint(10, 2_000)),
            source_system=source,
            country_code=customer.country,
            customer_id=customer.customer_id,
            correlation_id=uuid5(NAMESPACE, f"correlation:{self.seed}:{self.sequence}"),
            trace_id=stable_hash(f"trace:{self.seed}:{self.sequence}")[:32],
            payload=payload,
        )

    def _register_customer(self) -> EventEnvelope:
        index = len(self.customers) + 1
        country = self.random.choice(self.countries)
        customer_id = uuid5(NAMESPACE, f"customer:{self.seed}:{index}")
        risk_tier = self.random.betavariate(2.3, 4.0)
        income_band = self.random.choices(
            ["low", "lower_middle", "upper_middle", "high"],
            weights=[0.38, 0.37, 0.20, 0.05],
            k=1,
        )[0]
        customer = CustomerState(
            customer_id=customer_id,
            country=country,
            phone_hash=stable_hash(f"+{index:012d}"),
            risk_tier=risk_tier,
            income_band=income_band,
            network_tenure_days=self.random.randint(30, 3_500),
        )
        self.customers.append(customer)
        payload = CustomerRegistered(
            phone_hash=customer.phone_hash,
            age_band=self.random.choices(
                ["18-24", "25-34", "35-44", "45-54", "55+"],
                weights=[0.20, 0.40, 0.23, 0.12, 0.05],
                k=1,
            )[0],
            income_band=income_band,
            occupation=self.random.choice(
                ["farmer", "merchant", "salaried", "gig_worker", "other"]
            ),
        )
        return self._envelope(customer, payload, "identity")

    def _gsm_event(self, customer: CustomerState) -> EventEnvelope:
        activity = max(0.1, 1.2 - customer.risk_tier)
        payload = GsmUsage(
            call_duration_seconds=int(self.random.gammavariate(2.0, 500 * activity)),
            sms_count=int(self.random.gammavariate(1.4, 5 * activity)),
            data_mb=round(self.random.gammavariate(1.7, 80 * activity), 2),
            unique_contacts=self.random.randint(1, max(2, int(35 * activity))),
            airtime_topup_amount=round(self.random.gammavariate(1.6, 4 * activity), 2),
            network_tenure_days=customer.network_tenure_days,
        )
        return self._envelope(customer, payload, "gsm")

    def _money_event(self, customer: CustomerState) -> EventEnvelope:
        currency = CURRENCIES[customer.country]
        income_multiplier = {
            "low": 0.6,
            "lower_middle": 1.0,
            "upper_middle": 1.8,
            "high": 3.5,
        }[customer.income_band]
        base_amount = self.random.lognormvariate(3.2, 0.9) * income_multiplier
        amount = min(1_000_000, max(0.01, base_amount * AMOUNT_SCALE[currency]))
        payload = MobileMoneyTransaction(
            transaction_type=self.random.choices(
                ["cash_in", "cash_out", "p2p", "merchant_pay", "bill_pay"],
                weights=[0.18, 0.17, 0.30, 0.23, 0.12],
                k=1,
            )[0],
            amount=round(amount, 2),
            currency=currency,
            counterparty_hash=stable_hash(str(self.random.randint(1, 20_000)))[:32],
            channel=self.random.choices(["ussd", "app", "agent"], [0.58, 0.22, 0.20], k=1)[0],
        )
        return self._envelope(customer, payload, "mobile_money")

    def _device_event(self, customer: CustomerState) -> EventEnvelope:
        payload = DeviceSignal(
            device_hash=stable_hash(f"device:{customer.customer_id}")[:32],
            sim_slot_count=self.random.choices([1, 2, 3], [0.25, 0.70, 0.05], k=1)[0],
            device_age_months=self.random.randint(1, 72),
            is_rooted=self.random.random() < (0.02 + customer.risk_tier * 0.10),
            location_cell_changes_24h=int(self.random.expovariate(1 / 8)),
        )
        return self._envelope(customer, payload, "gsm")

    def _application_or_decision(self, customer: CustomerState) -> EventEnvelope:
        if customer.applications and self.random.random() < 0.48:
            application_id = self.random.choice(customer.applications)
            score = int(
                max(
                    0,
                    min(
                        1_000,
                        760 - customer.risk_tier * 480 + self.random.gauss(0, 45),
                    ),
                )
            )
            if score >= 560:
                decision = "approved"
                reason = "affordability_pass"
                customer.approved_applications.append(application_id)
            elif score >= 470:
                decision = "manual_review"
                reason = "thin_file"
            else:
                decision = "declined"
                reason = self.random.choice(["velocity_risk", "affordability_fail", "policy_limit"])
            scale = AMOUNT_SCALE[CURRENCIES[customer.country]]
            decision_payload = LoanDecision(
                application_id=application_id,
                decision=decision,
                score=score,
                approved_amount=(
                    round((50 + score * 0.35) * scale, 2) if decision == "approved" else 0
                ),
                interest_rate=(
                    round(0.08 + customer.risk_tier * 0.16, 4) if decision == "approved" else 0
                ),
                reason_code=reason,
            )
            return self._envelope(customer, decision_payload, "credit_engine")

        application_id = uuid5(NAMESPACE, f"application:{self.seed}:{self.sequence}")
        customer.applications.append(application_id)
        currency = CURRENCIES[customer.country]
        application_payload = LoanApplication(
            application_id=application_id,
            requested_amount=round(self.random.uniform(40, 420) * AMOUNT_SCALE[currency], 2),
            currency=currency,
            term_days=self.random.choice([7, 14, 30, 60, 90]),
            product_code=self.random.choices(
                ["nano", "working_capital", "personal"], [0.48, 0.32, 0.20], k=1
            )[0],
            stated_purpose=self.random.choice(
                ["inventory", "emergency", "education", "agriculture", "other"]
            ),
        )
        return self._envelope(customer, application_payload, "credit_engine")

    def _repayment_event(self, customer: CustomerState) -> EventEnvelope:
        application_id = self.random.choice(customer.approved_applications)
        late_probability = 0.05 + customer.risk_tier * 0.38
        is_late = self.random.random() < late_probability
        days_past_due = self.random.randint(1, 90) if is_late else 0
        currency = CURRENCIES[customer.country]
        payload = Repayment(
            loan_id=uuid5(NAMESPACE, f"loan:{application_id}"),
            application_id=application_id,
            amount=round(self.random.uniform(15, 150) * AMOUNT_SCALE[currency], 2),
            currency=currency,
            days_past_due=days_past_due,
            payment_status=(
                self.random.choice(["late", "partial"])
                if is_late
                else self.random.choice(["on_time", "settled"])
            ),
        )
        return self._envelope(customer, payload, "loan_ledger")
