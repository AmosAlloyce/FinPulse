# Eight-minute interview demo

## 0:00–1:00 — Frame the problem

“Digital credit decisions depend on signals arriving from unreliable, globally distributed GSM and financial systems. FinPulse turns those signals into a governed credit data product while preserving replayability, privacy, and operational visibility.”

Show the architecture diagram in the README. Point out that the same logical design runs locally and maps to managed AWS services.

## 1:00–2:00 — Prove the source is realistic

```bash
.venv/bin/finpulse emit --count 3
```

Highlight UTC event time versus ingestion time, schema versioning, source, traceability, and pseudonymous identifiers. Explain that the generator maintains customer/application/decision/repayment relationships and latent risk.

## 2:00–3:00 — Show the live stream

Open the Kafka console at http://localhost:8080 and the `finpulse.events.raw.v1` topic. Explain customer-key ordering, six partitions, idempotent producer settings, and deliberate malformed-event injection.

Then open MinIO at http://localhost:9001 and show bronze, silver, quarantine, and checkpoint prefixes.

## 3:00–4:00 — Demonstrate failure handling

Open `finpulse.events.dlq.v1`. Find the `unsupported_schema_version` test message. Explain why poison messages do not stop the pipeline and how an operator can fix and replay them.

In Grafana, show quarantine rate, latest event age, Spark throughput, and API query latency.

## 4:00–5:30 — Connect engineering to business

Open http://localhost:8501:

1. Executive overview: event throughput, application funnel, approval rate, PAR30.
2. Country portfolio: compare market volume, approvals, and risk.
3. Risk and decisions: explain score distribution and model monitoring.
4. Platform operations: show freshness and recent traceable events.

Make the point that one platform serves portfolio managers, decision scientists, and operators without copying conflicting logic into each dashboard.

## 5:30–6:30 — Show data product quality

Open the Airflow DAG at http://localhost:8088. Walk through freshness → source volume → dbt build → dbt tests → audit publication → table analysis.

Open `dbt/models/marts/fct_credit_portfolio.sql` and its schema tests. Explain the latest-decision rule and application-grain guarantee.

## 6:30–7:15 — Show engineering discipline

```bash
make test
make lint
```

Point out contract round trips, referential generator checks, business quality rules, complete local data-product tests, container build matrix, and Terraform validation.

## 7:15–8:00 — Scale and tradeoffs

Show `infra/terraform`. Local components map to MSK Serverless, S3/Glue, EMR Serverless, Redshift Serverless, and DynamoDB. Mention Kubernetes HPA/PDB, Spark dynamic allocation, KMS, private networking, and workload identity.

Close with the deliberate tradeoff: PostgreSQL and MinIO keep the demo affordable, while interfaces and SQL remain close enough to managed AWS services to show a credible migration path.

