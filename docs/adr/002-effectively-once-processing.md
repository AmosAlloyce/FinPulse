# ADR 002: Prefer effectively-once outcomes over distributed transactions

Status: accepted

## Decision

Use at-least-once transport with globally stable event IDs, Spark checkpoints and watermarks, primary-key/idempotent warehouse writes, immutable bronze history, and partition-scoped backfills.

## Consequences

The design remains practical across Kafka, S3, and Redshift without a fragile cross-system transaction coordinator. Every new sink must document its deduplication key and replay behavior.

