from __future__ import annotations

import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from finpulse.config import get_settings
from finpulse.streaming.schema import event_schema


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotent FinPulse bronze-to-silver backfill")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    args = parser.parse_args()
    settings = get_settings()
    spark = SparkSession.builder.appName("finpulse-backfill").getOrCreate()
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")

    bronze = spark.read.parquet(f"s3a://{settings.s3_bucket}/bronze/events")
    parsed = (
        bronze.filter(F.col("ingestion_date").between(args.start_date, args.end_date))
        .withColumn("event", F.from_json("raw_value", event_schema()))
        .select("event.*")
        .filter(F.col("event_id").isNotNull())
        .dropDuplicates(["event_id"])
        .withColumn("processing_date", F.to_date("occurred_at"))
        .withColumn("payload_json", F.to_json("payload"))
    )
    output = f"s3a://{settings.s3_bucket}/silver/events"
    (
        parsed.select(
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
        )
        .write.mode("overwrite")
        .partitionBy("processing_date", "country_code", "event_type")
        .parquet(output)
    )
    spark.stop()


if __name__ == "__main__":
    main()
