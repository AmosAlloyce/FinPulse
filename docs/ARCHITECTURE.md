# Architecture

## Design goals

FinPulse is optimised for correctness under replay, observable freshness, independently scalable components, and a clear boundary between raw source facts and reusable analytical products.

| Layer | Responsibility | Scale strategy | Failure boundary |
|---|---|---|---|
| Kafka/MSK | Durable globally distributed ingress | Add partitions; key by customer | Source retries do not block processors |
| Spark streaming | Parse, validate, watermark, deduplicate, route | Add executors; cap offsets per trigger | Bad data goes to DLQ, not job failure |
| S3 lakehouse | Immutable history and replay source | Object partitioning by date/country/type | Compute is disposable |
| Warehouse | Low-latency portfolio queries | Redshift Serverless RPUs and sort/distribution design | Rebuildable from silver data |
| dbt | Business semantics and tests | Parallel model graph | Quality gate blocks publication |
| Airflow | Dependency, retry, audit, backfill | Independent workers/schedulers | One failed product does not corrupt raw data |
| API/BI | Governed consumption | Stateless horizontal scaling | Read-only, separately deployable |

## Medallion layout

```text
s3://finpulse-lakehouse/
├── bronze/events/ingestion_date=YYYY-MM-DD/kafka_partition=N/
├── silver/events/processing_date=YYYY-MM-DD/country_code=KEN/event_type=gsm_usage/
├── quarantine/events/quality_reason=invalid_json/
├── gold/credit_portfolio/decision_date=YYYY-MM-DD/
└── checkpoints/credit-events-v1/{bronze,silver,quarantine}/
```

Bronze is append-only and retains Kafka coordinates. Silver is validated, deduplicated, and partitioned for common pruning dimensions. Gold is owned by a named data product and carries tested business semantics.

## Processing semantics

Kafka and Spark provide at-least-once delivery around external sinks. FinPulse reaches effectively-once results through stable event IDs, checkpointed offsets, event-time deduplication, warehouse primary keys, and idempotent partition-scoped backfills. See ADR 002.

## Partitioning

- Kafka: six local partitions, expanded based on measured peak throughput; customer ID is the key to preserve per-customer ordering.
- Bronze: ingestion date and Kafka partition preserve source replay locality.
- Silver: event date, country, and type match the dominant access and backfill patterns.
- Warehouse: indexes locally; production Redshift would use `application_id`/`customer_id` distribution decisions based on table size and join telemetry, with time-oriented sort keys.

## Security

The cloud design uses private subnets, IAM authentication for MSK, workload identity, KMS rotation, bucket public-access blocks, Redshift enhanced VPC routing, Secrets Manager, encrypted SNS, and least-privilege service roles. Customer identifiers are pseudonymous and raw phone/device values are hashed before analytics ingress.

