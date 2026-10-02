# Interactive FinPulse portfolio demo

The browser app turns this repository's portable pipeline into an inspectable, isolated sandbox. It is a second entry point into the existing project. The original Kafka/Redpanda, Spark, dbt, Airflow, Streamlit, AWS and Kubernetes files remain available as the distributed reference architecture; none of those services are started by the web demo.

The backend actually imports and executes:

- `SyntheticEventGenerator` for deterministic, related customers, applications, decisions and repayments;
- `EventEnvelope` for the original versioned Pydantic contract;
- `validate_business_rules` and `QualityReport` for business validation and warning/error semantics;
- `LOCAL_SCHEMA`, `LocalPipeline._load_event` and its SQL marts for dimensional loading and analytics.

All customers and transactions are synthetic. The app displays generated sample loan decisions; it neither evaluates real borrowers nor makes a live lending decision. There is no external AI call, arbitrary SQL endpoint, upload or custom raw-event ingestion in this service.

## Local startup

Use Python 3.12+ and Node 22. The demo has a small, separate Python dependency file so the interactive path does not install Spark or start the distributed stack.

```bash
python3 -m venv .venv-demo
.venv-demo/bin/pip install -r requirements.demo.txt
cd web
npm ci
npm run build
cd ..
PUBLIC_ORIGIN=http://127.0.0.1:5174 PYTHONPATH=src .venv-demo/bin/uvicorn finpulse.demo.main:app --host 127.0.0.1 --port 8011
```

For frontend development, run `npm run dev -- --host 127.0.0.1 --port 5174` in `web/` in another terminal. Match `PUBLIC_ORIGIN` to the exact Vite origin shown in its startup log; this is required when the proxy rewrites the Host header. Vite's public base is `/finpulse/`; its `/finpulse/api` proxy strips the prefix and forwards to port 8011. This is also the public deployment model. The API cookie is scoped to `/finpulse`, so a direct browser opened at `http://localhost:8011/` is **not** the intended interactive entry point. To test the stripped standalone app directly, explicitly set `COOKIE_PATH=/` and match its origin; keep `/finpulse` for the portfolio deployment.

`GET http://127.0.0.1:8011/api/health` does not create a session. It reports the actual standalone mode and SQLite storage.

## Demonstration flow

1. Open `/finpulse/`. A fresh visitor warehouse receives 980 deliveries: 966 accepted facts, eight duplicate deliveries and six quarantined records. Six accepted events also carry a freshness warning. The sample includes 47 customers across Kenya, Uganda, Ghana, Tanzania and Zambia.
2. Inspect a delivery in Event explorer. Its raw contract remains available, with its canonical event ID, pseudonymous customer token, trace ID, quality issues and related customer events.
3. Stage a scenario: normal activity, duplicate delivery, known schema/timestamp defects, or late arrival. The warehouse does not change at this point; only bronze gains pending deliveries.
4. Run Pipeline studio. Contract validation, business checks, event-ID deduplication, the original dimensional loader and SQL mart queries execute against the pending records. The trace reports actual counts and measured durations.
5. Review an open Quality lab exception. Approval restores only the original field value recorded when the synthetic defect was injected. The restored envelope passes the same contract and business checks before loading. The bad raw delivery remains immutable, and an audit event links it to the corrected delivery. Repeated approval is rejected.
6. Explore Market insights. Counts and rates may be compared, while monetary values stay grouped by KES, UGX, GHS, TZS or ZMW. PAR30 is an observed sample repayment statistic, not an exposure-weighted production risk calculation. Markets without repayment observations show no PAR30 value.
7. Open Data products. Each preview is read from its actual SQL view or table, displays its complete schema and exports the full bounded dataset. Validated facts and all delivery history are distinct datasets.

Country selection filters analytics, event listings, quarantine and product previews/counts. The workspace health `stats` always describe the entire visitor warehouse. Event lists are paginated; CSV exports include all rows within workspace limits.

## State, bounds and failure behavior

Each visitor receives an opaque HttpOnly, SameSite=Lax cookie. It becomes Secure on HTTPS. A separate SQLite file contains that visitor's delivery history, typed facts, marts, runs and audit. Cookie identity and warehouse state survive a process/container restart until expiry. This is isolation for a public synthetic sandbox, not production user authentication.

- Maximum 40 active workspaces, with a two-hour sliding expiry; expired databases are removed when new API traffic arrives.
- Maximum 2,500 deliveries per workspace, 100 per simulation, 40 pipeline runs and 100 audit entries. Capacity is reserved for known corrections, including invalid deliveries still pending validation.
- Maximum 150 requests and 40 mutations per minute per visitor, and ten new workspaces per minute per IP. Creation-rate buckets are bounded.
- Eight database operations can execute concurrently. Each visitor's operations serialize; a conflicting request waits at most two seconds before receiving a retryable error.
- Mutation bodies are limited to 8 KB, require JSON and pass origin checks. There is no client-supplied correction payload. Fixed dataset names and parameterized filters prevent arbitrary SQL execution.
- Mutations, replay and reset use SQLite transactions. Failures roll back uncommitted work. CSV output neutralizes spreadsheet formula prefixes.

The generator state is reconstructed from its seed and sequence; no untrusted pickle data is used. Long-lived active workspaces are bounded by their event/run limits. No background queue or unbounded worker pool is created.

## Deployment configuration

`Dockerfile.demo` builds `web/dist` and runs only FastAPI/Uvicorn on port 8011, as user 10001. `Dockerfile.demo.dockerignore` excludes secrets, virtual environments, node_modules, generated artifacts and the large reference infrastructure trees from that image's build context.

`compose.demo.yaml` configures a read-only filesystem, a persistent `/app/data` volume, a 32 MB temporary filesystem, dropped capabilities, a 512 MB memory budget and one CPU. Its host port binds only to loopback. The service joins the existing external network `three-dollar-motel_default` with the alias `finpulse-app`.

The portfolio proxy must redirect `/finpulse` to `/finpulse/`, then strip the prefix before forwarding:

```caddyfile
handle_path /finpulse/* {
    reverse_proxy finpulse-app:8011
}
```

Set `PUBLIC_ORIGIN` to the exact public origin, for example `https://alloyce-amos.duckdns.org`. Forwarded headers are trusted only because this service sits on the private proxy network; do not expose its port directly to the Internet. `FINPULSE_DATA_DIR`, `FINPULSE_WEB_DIST` and `COOKIE_PATH` configure storage, built assets and the public cookie scope.

The container configuration has been validated separately from deployment. No distributed infrastructure needs to be started to demonstrate these interactions. See [WEB_API.md](WEB_API.md) for the exact client contract.

## Verification

```bash
.venv-demo/bin/pip install 'pytest>=8.3,<9' 'pytest-cov>=5,<7' 'httpx>=0.27,<1' 'pydantic-settings>=2.5,<3' 'ruff>=0.7,<1'
PYTHONPATH=src .venv-demo/bin/python -m pytest --cov=finpulse --cov-report=xml --cov-fail-under=75
.venv-demo/bin/ruff check src tests airflow/dags
.venv-demo/bin/ruff format --check src tests airflow/dags
docker compose -f compose.demo.yaml config --quiet
```

Tests cover the original contracts/generator/quality/local pipeline plus visitor isolation, restart persistence, immutable raw records, explicit and idempotent replay, duplicate suppression, late-warning retention, currency separation, full product exports, input boundaries, capacity/expiry, transaction rollback and static deep links.
