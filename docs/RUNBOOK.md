# Operations runbook

## Service-level objectives

| SLI | Target | Warning | Critical |
|---|---:|---:|---:|
| Latest event age | < 60 s | 60–300 s | > 300 s |
| Valid-event acceptance | ≥ 99% | 98–99% | < 98% |
| Streaming p95 processing lag | < 30 s | 30–120 s | > 120 s |
| API p95 query latency | < 500 ms | 0.5–2 s | > 2 s |
| Daily mart availability | 03:00 UTC | 15 min late | 60 min late |

## Consumer lag or stale events

1. Confirm producer health and Kafka partition ingress in Redpanda Console.
2. Inspect `finpulse_stream_batch_duration_seconds` and Spark executor memory.
3. Compare ingress rate with `maxOffsetsPerTrigger` and processed rate.
4. Check MinIO/S3 and warehouse connectivity before adding compute.
5. If the system is healthy but undersized, scale executors or increase Spark Operator limits.
6. Do not delete checkpoints. Recreate them only for an intentional full replay.

## Rising quarantine rate

1. Group DLQ events by `quality_reason`.
2. Compare `schema_version` and producing source deployment time.
3. For compatible additions, release a consumer schema update before the producer.
4. For source defects, pause that source, preserve raw events, deploy the correction, and replay the DLQ with original event IDs.
5. Record the incident and add the failing sample as a contract test.

## Warehouse unavailable

Spark continues to retain bronze input. Stop or allow the failing silver/warehouse query to retry; do not advance checkpoints past a partially committed external sink. Restore connectivity, verify primary-key constraints, then restart. Stable event IDs make replay safe.

## Date backfill

```bash
spark-submit src/finpulse/batch/backfill.py \
  --start-date 2026-07-01 \
  --end-date 2026-07-07
```

Validate row counts and quality results before running `dbt build`. Backfills use dynamic partition overwrite and must never target an unbounded path.

## Local recovery

```bash
docker compose ps
docker compose logs --tail=200 stream-processor
docker compose restart stream-processor
make smoke
```

Destroy local volumes only when losing all local demo data is explicitly acceptable: `docker compose down -v`.

