from __future__ import annotations


def event_schema():  # type: ignore[no-untyped-def]
    """Return the Spark schema lazily so the base package does not require PySpark."""

    from pyspark.sql.types import (
        BooleanType,
        DoubleType,
        IntegerType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    payload = StructType(
        [
            StructField("event_type", StringType()),
            StructField("phone_hash", StringType()),
            StructField("age_band", StringType()),
            StructField("income_band", StringType()),
            StructField("occupation", StringType()),
            StructField("consent_version", StringType()),
            StructField("call_duration_seconds", IntegerType()),
            StructField("sms_count", IntegerType()),
            StructField("data_mb", DoubleType()),
            StructField("unique_contacts", IntegerType()),
            StructField("airtime_topup_amount", DoubleType()),
            StructField("network_tenure_days", IntegerType()),
            StructField("transaction_type", StringType()),
            StructField("amount", DoubleType()),
            StructField("currency", StringType()),
            StructField("counterparty_hash", StringType()),
            StructField("channel", StringType()),
            StructField("device_hash", StringType()),
            StructField("sim_slot_count", IntegerType()),
            StructField("device_age_months", IntegerType()),
            StructField("is_rooted", BooleanType()),
            StructField("location_cell_changes_24h", IntegerType()),
            StructField("application_id", StringType()),
            StructField("requested_amount", DoubleType()),
            StructField("term_days", IntegerType()),
            StructField("product_code", StringType()),
            StructField("stated_purpose", StringType()),
            StructField("decision", StringType()),
            StructField("score", IntegerType()),
            StructField("approved_amount", DoubleType()),
            StructField("interest_rate", DoubleType()),
            StructField("reason_code", StringType()),
            StructField("model_version", StringType()),
            StructField("loan_id", StringType()),
            StructField("days_past_due", IntegerType()),
            StructField("payment_status", StringType()),
        ]
    )
    return StructType(
        [
            StructField("event_id", StringType()),
            StructField("schema_version", StringType()),
            StructField("event_type", StringType()),
            StructField("occurred_at", TimestampType()),
            StructField("ingested_at", TimestampType()),
            StructField("source_system", StringType()),
            StructField("country_code", StringType()),
            StructField("customer_id", StringType()),
            StructField("correlation_id", StringType()),
            StructField("trace_id", StringType()),
            StructField("payload", payload),
        ]
    )
