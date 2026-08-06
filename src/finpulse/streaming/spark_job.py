from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

import psycopg
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from finpulse.config import Settings, get_settings
from finpulse.logging import configure_logging
from finpulse.streaming.schema import event_schema

LOGGER = logging.getLogger(__name__)
VALID_EVENT_TYPES = [
    "customer_registered",
    "gsm_usage",
    "mobile_money_transaction",
    "device_signal",
    "loan_application",
    "loan_decision",
    "repayment",
]

PROCESSED = Counter("finpulse_stream_processed_total", "Accepted events", ["event_type"])
QUARANTINED = Counter("finpulse_stream_quarantined_total", "Quarantined events", ["reason"])
BATCH_SIZE = Gauge("finpulse_stream_batch_records", "Records in the latest micro-batch")
BATCH_DURATION = Histogram("finpulse_stream_batch_duration_seconds", "Micro-batch duration")
LATEST_EVENT_UNIX = Gauge("finpulse_stream_latest_event_unix", "Newest processed event timestamp")


def build_spark(settings: Settings) -> SparkSession:
    builder = (
        SparkSession.builder.appName("finpulse-credit-events-v1")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.streaming.metricsEnabled", "true")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.hadoop.fs.s3a.endpoint", settings.s3_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", settings.aws_access_key_id)
        .config("spark.hadoop.fs.s3a.secret.key", settings.aws_secret_access_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    )
    return builder.getOrCreate()


def parse_stream(raw: DataFrame) -> DataFrame:
    parsed = raw.select(
        F.col("key").cast("string").alias("kafka_key"),
        F.col("value").cast("string").alias("raw_value"),
        F.col("timestamp").alias("kafka_timestamp"),
        F.col("partition").alias("kafka_partition"),
        F.col("offset").alias("kafka_offset"),
        F.from_json(F.col("value").cast("string"), event_schema()).alias("event"),
    ).select("*", "event.*")

    return parsed.withColumn(
        "quality_reason",
        F.when(F.col("event").isNull(), "invalid_json")
        .when(F.col("event_id").isNull(), "missing_event_id")
        .when(F.col("schema_version") != "1.0", "unsupported_schema_version")
        .when(~F.col("event_type").isin(VALID_EVENT_TYPES), "unknown_event_type")
        .when(F.col("payload.event_type") != F.col("event_type"), "payload_type_mismatch")
        .when(F.col("customer_id").isNull(), "missing_customer_id")
        .when(F.col("country_code").isNull(), "missing_country")
        .when(F.col("occurred_at").isNull(), "missing_occurred_at")
        .when(F.col("ingested_at") < F.col("occurred_at"), "invalid_event_time")
        .when(
            (F.col("event_type") == "mobile_money_transaction") & (F.col("payload.amount") <= 0),
            "invalid_transaction_amount",
        )
        .when(
            (F.col("event_type") == "loan_application") & (F.col("payload.requested_amount") <= 0),
            "invalid_requested_amount",
        ),
    )


def upsert_partition(rows: Iterator[Any], dsn: str, table: str, columns: list[str]) -> None:
    """Commit one Spark partition idempotently using event_id uniqueness."""

    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(columns)
    statement = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        buffer: list[tuple[Any, ...]] = []
        for row in rows:
            buffer.append(tuple(row))
            if len(buffer) >= 1_000:
                cursor.executemany(statement, buffer)
                buffer.clear()
        if buffer:
            cursor.executemany(statement, buffer)


def write_table(batch: DataFrame, table: str, columns: list[Any], settings: Settings) -> None:
    if batch.rdd.isEmpty():
        return
    selected = batch.select(*columns)
    selected_columns = selected.columns
    warehouse_dsn = settings.warehouse_dsn
    selected.foreachPartition(
        lambda rows: upsert_partition(rows, warehouse_dsn, table, selected_columns)
    )


def process_good_batch(batch: DataFrame, batch_id: int, settings: Settings) -> None:
    started = time.monotonic()
    batch = batch.persist()
    count = batch.count()
    if count == 0:
        batch.unpersist()
        return

    BATCH_SIZE.set(count)
    newest = batch.agg(F.max("occurred_at")).first()[0]
    if newest:
        LATEST_EVENT_UNIX.set(newest.timestamp())

    silver = batch.select(
        "event_id",
        "schema_version",
        "event_type",
        "occurred_at",
        "ingested_at",
        "source_system",
        "country_code",
        "customer_id",
        "correlation_id",
        "trace_id",
        F.to_json("payload").alias("payload_json"),
        F.to_date("occurred_at").alias("processing_date"),
    )
    (
        silver.write.mode("append")
        .partitionBy("processing_date", "country_code", "event_type")
        .parquet(f"s3a://{settings.s3_bucket}/silver/events")
    )
    write_table(
        silver,
        "warehouse.event_fact",
        [
            "event_id",
            "schema_version",
            "event_type",
            "occurred_at",
            "ingested_at",
            "source_system",
            "country_code",
            "customer_id",
            "correlation_id",
            "trace_id",
            "payload_json",
            "processing_date",
        ],
        settings,
    )

    event_counts = batch.groupBy("event_type").count().collect()
    for row in event_counts:
        PROCESSED.labels(event_type=row["event_type"]).inc(row["count"])

    base = ["event_id", "customer_id", "occurred_at", "country_code"]
    mappings = {
        "customer_registered": (
            "warehouse.customers",
            [
                *base,
                F.col("payload.phone_hash").alias("phone_hash"),
                F.col("payload.age_band").alias("age_band"),
                F.col("payload.income_band").alias("income_band"),
                F.col("payload.occupation").alias("occupation"),
                F.col("payload.consent_version").alias("consent_version"),
            ],
        ),
        "gsm_usage": (
            "warehouse.gsm_usage",
            [
                *base,
                F.col("payload.call_duration_seconds").alias("call_duration_seconds"),
                F.col("payload.sms_count").alias("sms_count"),
                F.col("payload.data_mb").alias("data_mb"),
                F.col("payload.unique_contacts").alias("unique_contacts"),
                F.col("payload.airtime_topup_amount").alias("airtime_topup_amount"),
                F.col("payload.network_tenure_days").alias("network_tenure_days"),
            ],
        ),
        "mobile_money_transaction": (
            "warehouse.mobile_money_transactions",
            [
                *base,
                F.col("payload.transaction_type").alias("transaction_type"),
                F.col("payload.amount").alias("amount"),
                F.col("payload.currency").alias("currency"),
                F.col("payload.counterparty_hash").alias("counterparty_hash"),
                F.col("payload.channel").alias("channel"),
            ],
        ),
        "loan_application": (
            "warehouse.loan_applications",
            [
                *base,
                F.col("payload.application_id").alias("application_id"),
                F.col("payload.requested_amount").alias("requested_amount"),
                F.col("payload.currency").alias("currency"),
                F.col("payload.term_days").alias("term_days"),
                F.col("payload.product_code").alias("product_code"),
                F.col("payload.stated_purpose").alias("stated_purpose"),
            ],
        ),
        "loan_decision": (
            "warehouse.loan_decisions",
            [
                *base,
                F.col("payload.application_id").alias("application_id"),
                F.col("payload.decision").alias("decision"),
                F.col("payload.score").alias("score"),
                F.col("payload.approved_amount").alias("approved_amount"),
                F.col("payload.interest_rate").alias("interest_rate"),
                F.col("payload.reason_code").alias("reason_code"),
                F.col("payload.model_version").alias("model_version"),
            ],
        ),
        "repayment": (
            "warehouse.repayments",
            [
                *base,
                F.col("payload.loan_id").alias("loan_id"),
                F.col("payload.application_id").alias("application_id"),
                F.col("payload.amount").alias("amount"),
                F.col("payload.currency").alias("currency"),
                F.col("payload.days_past_due").alias("days_past_due"),
                F.col("payload.payment_status").alias("payment_status"),
            ],
        ),
    }
    for event_type, (table, columns) in mappings.items():
        write_table(batch.filter(F.col("event_type") == event_type), table, columns, settings)

    batch.unpersist()
    BATCH_DURATION.observe(time.monotonic() - started)
    LOGGER.info("micro-batch committed", extra={"batch_id": batch_id, "records": count})


def process_bad_batch(batch: DataFrame, batch_id: int, settings: Settings) -> None:
    batch = batch.persist()
    if batch.rdd.isEmpty():
        batch.unpersist()
        return
    for row in batch.groupBy("quality_reason").count().collect():
        QUARANTINED.labels(reason=row["quality_reason"]).inc(row["count"])
    output = batch.select(
        F.coalesce("kafka_key", F.lit("unknown")).cast("string").alias("key"),
        F.to_json(
            F.struct(
                "quality_reason",
                "raw_value",
                "kafka_timestamp",
                "kafka_partition",
                "kafka_offset",
            )
        ).alias("value"),
    )
    (
        output.write.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("topic", settings.kafka_dlq_topic)
        .save()
    )
    (
        batch.select(
            "quality_reason",
            "raw_value",
            "kafka_timestamp",
            "kafka_partition",
            "kafka_offset",
        )
        .write.mode("append")
        .partitionBy("quality_reason")
        .parquet(f"s3a://{settings.s3_bucket}/quarantine/events")
    )
    LOGGER.warning("quarantine batch committed", extra={"batch_id": batch_id})
    batch.unpersist()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    start_http_server(9108)
    spark = build_spark(settings)
    spark.sparkContext.setLogLevel("WARN")

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("subscribe", settings.kafka_raw_topic)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .option("maxOffsetsPerTrigger", 100_000)
        .load()
    )
    parsed = parse_stream(raw)

    bronze_query = (
        parsed.select(
            "raw_value",
            "kafka_timestamp",
            "kafka_partition",
            "kafka_offset",
            F.to_date("kafka_timestamp").alias("ingestion_date"),
        )
        .writeStream.format("parquet")
        .option("path", f"s3a://{settings.s3_bucket}/bronze/events")
        .option("checkpointLocation", f"{settings.spark_checkpoint_location}/bronze")
        .partitionBy("ingestion_date", "kafka_partition")
        .outputMode("append")
        .start()
    )
    good = (
        parsed.filter(F.col("quality_reason").isNull())
        .withWatermark("ingested_at", "24 hours")
        .dropDuplicates(["event_id"])
    )
    good_query = (
        good.writeStream.foreachBatch(lambda frame, idx: process_good_batch(frame, idx, settings))
        .option("checkpointLocation", f"{settings.spark_checkpoint_location}/silver")
        .trigger(processingTime="10 seconds")
        .start()
    )
    bad_query = (
        parsed.filter(F.col("quality_reason").isNotNull())
        .writeStream.foreachBatch(lambda frame, idx: process_bad_batch(frame, idx, settings))
        .option("checkpointLocation", f"{settings.spark_checkpoint_location}/quarantine")
        .trigger(processingTime="10 seconds")
        .start()
    )

    LOGGER.info(
        "structured streaming queries started",
        extra={"query_ids": [str(query.id) for query in [bronze_query, good_query, bad_query]]},
    )
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
