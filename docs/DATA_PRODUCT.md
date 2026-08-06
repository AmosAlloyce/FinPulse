# Credit Portfolio data product

## Owner and consumers

- Owner: Data Platform
- Domain partner: Credit Portfolio
- Consumers: portfolio managers, decision scientists, finance operations, risk monitoring, BI

## Contract

Primary published model: `analytics.fct_credit_portfolio`, one row per loan application with the latest known decision and aggregated repayment performance.

Key guarantees:

- `application_id` is unique and non-null.
- customer IDs are pseudonymous and relate to the governed customer dimension.
- scores remain in the 0–1000 model range.
- decisions use a controlled vocabulary.
- publication is blocked if freshness, volume, relationships, uniqueness, or accepted-range tests fail.
- raw events remain replayable if business semantics change.

## Lifecycle

1. Discover: portfolio and decision-science questions define event and mart grains.
2. Design: contract, ownership, SLOs, access patterns, privacy, and backfill plan.
3. Build: source → Kafka → Spark → lakehouse/warehouse → dbt.
4. Verify: contract tests, quality rules, dbt tests, reconciliation, performance.
5. Publish: Airflow gates the daily mart and writes an audit record.
6. Operate: monitor freshness, lag, quarantine rate, query latency, model distribution.
7. Evolve: additive schema versions first; breaking changes use parallel topics/models and migration windows.
8. Retire: notify consumers, freeze writes, preserve retention-required history, remove access.

