# ADR 003: Use interface parity rather than identical local cloud services

Status: accepted

## Decision

Use Redpanda for the Kafka protocol, MinIO for S3 APIs, PostgreSQL for relational marts, and local Spark/Airflow containers. Provision managed AWS equivalents with Terraform.

## Consequences

The portfolio remains affordable and runnable on a laptop. Some Redshift/MSK/IAM behavior requires a cloud integration environment, so CI validates infrastructure syntax while cloud smoke tests belong in a controlled account.

