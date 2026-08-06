CREATE DATABASE airflow;

CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS observability;

CREATE TABLE IF NOT EXISTS warehouse.event_fact (
    event_id UUID PRIMARY KEY,
    schema_version VARCHAR(10) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    source_system VARCHAR(64) NOT NULL,
    country_code CHAR(3) NOT NULL,
    customer_id UUID NOT NULL,
    correlation_id UUID NOT NULL,
    trace_id VARCHAR(64) NOT NULL,
    payload_json TEXT NOT NULL,
    processing_date DATE NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_event_fact_customer_time
    ON warehouse.event_fact(customer_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_event_fact_type_time
    ON warehouse.event_fact(event_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_event_fact_processing_date
    ON warehouse.event_fact(processing_date);

CREATE TABLE IF NOT EXISTS warehouse.customers (
    event_id UUID PRIMARY KEY,
    customer_id UUID NOT NULL UNIQUE,
    occurred_at TIMESTAMPTZ NOT NULL,
    country_code CHAR(3) NOT NULL,
    phone_hash CHAR(64) NOT NULL,
    age_band VARCHAR(16) NOT NULL,
    income_band VARCHAR(32) NOT NULL,
    occupation VARCHAR(32) NOT NULL,
    consent_version VARCHAR(16) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_customers_country ON warehouse.customers(country_code);

CREATE TABLE IF NOT EXISTS warehouse.gsm_usage (
    event_id UUID PRIMARY KEY,
    customer_id UUID NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    country_code CHAR(3) NOT NULL,
    call_duration_seconds INTEGER NOT NULL CHECK (call_duration_seconds >= 0),
    sms_count INTEGER NOT NULL CHECK (sms_count >= 0),
    data_mb DOUBLE PRECISION NOT NULL CHECK (data_mb >= 0),
    unique_contacts INTEGER NOT NULL CHECK (unique_contacts >= 0),
    airtime_topup_amount NUMERIC(20, 4) NOT NULL CHECK (airtime_topup_amount >= 0),
    network_tenure_days INTEGER NOT NULL CHECK (network_tenure_days >= 0)
);
CREATE INDEX IF NOT EXISTS ix_gsm_customer_time
    ON warehouse.gsm_usage(customer_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS warehouse.mobile_money_transactions (
    event_id UUID PRIMARY KEY,
    customer_id UUID NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    country_code CHAR(3) NOT NULL,
    transaction_type VARCHAR(32) NOT NULL,
    amount NUMERIC(20, 4) NOT NULL CHECK (amount > 0),
    currency CHAR(3) NOT NULL,
    counterparty_hash VARCHAR(64) NOT NULL,
    channel VARCHAR(16) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_money_customer_time
    ON warehouse.mobile_money_transactions(customer_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS warehouse.loan_applications (
    event_id UUID PRIMARY KEY,
    customer_id UUID NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    country_code CHAR(3) NOT NULL,
    application_id UUID NOT NULL UNIQUE,
    requested_amount NUMERIC(20, 4) NOT NULL CHECK (requested_amount > 0),
    currency CHAR(3) NOT NULL,
    term_days INTEGER NOT NULL,
    product_code VARCHAR(32) NOT NULL,
    stated_purpose VARCHAR(32) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_applications_customer_time
    ON warehouse.loan_applications(customer_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS warehouse.loan_decisions (
    event_id UUID PRIMARY KEY,
    customer_id UUID NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    country_code CHAR(3) NOT NULL,
    application_id UUID NOT NULL,
    decision VARCHAR(32) NOT NULL,
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 1000),
    approved_amount NUMERIC(20, 4) NOT NULL CHECK (approved_amount >= 0),
    interest_rate NUMERIC(8, 6) NOT NULL CHECK (interest_rate BETWEEN 0 AND 1),
    reason_code VARCHAR(64) NOT NULL,
    model_version VARCHAR(64) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_decisions_application_time
    ON warehouse.loan_decisions(application_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS warehouse.repayments (
    event_id UUID PRIMARY KEY,
    customer_id UUID NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    country_code CHAR(3) NOT NULL,
    loan_id UUID NOT NULL,
    application_id UUID NOT NULL,
    amount NUMERIC(20, 4) NOT NULL CHECK (amount > 0),
    currency CHAR(3) NOT NULL,
    days_past_due INTEGER NOT NULL CHECK (days_past_due >= 0),
    payment_status VARCHAR(16) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_repayments_application_time
    ON warehouse.repayments(application_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS observability.pipeline_runs (
    run_id BIGSERIAL PRIMARY KEY,
    pipeline_name VARCHAR(128) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    input_rows BIGINT,
    output_rows BIGINT,
    quarantined_rows BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS observability.data_quality_results (
    result_id BIGSERIAL PRIMARY KEY,
    run_id BIGINT REFERENCES observability.pipeline_runs(run_id),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dataset_name VARCHAR(128) NOT NULL,
    rule_name VARCHAR(128) NOT NULL,
    status VARCHAR(16) NOT NULL,
    observed_value DOUBLE PRECISION,
    threshold_value DOUBLE PRECISION,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE OR REPLACE VIEW analytics.vw_realtime_kpis AS
WITH latest_decision AS (
    SELECT DISTINCT ON (application_id)
        application_id, decision, score, approved_amount, model_version
    FROM warehouse.loan_decisions
    ORDER BY application_id, occurred_at DESC
), repayment_by_application AS (
    SELECT
        application_id,
        SUM(amount) AS repaid_amount,
        MAX(days_past_due) AS max_days_past_due,
        BOOL_OR(days_past_due > 30) AS ever_par30
    FROM warehouse.repayments
    GROUP BY application_id
)
SELECT
    COUNT(DISTINCT a.customer_id) AS applicants,
    COUNT(*) AS applications,
    COUNT(d.application_id) AS decisions,
    COUNT(*) FILTER (WHERE d.decision = 'approved') AS approvals,
    COUNT(*) FILTER (WHERE r.application_id IS NOT NULL) AS loans_with_repayment,
    ROUND(100.0 * COUNT(*) FILTER (WHERE d.decision = 'approved')
        / NULLIF(COUNT(d.application_id), 0), 2) AS approval_rate_pct,
    COALESCE(SUM(d.approved_amount), 0) AS approved_value_local,
    ROUND(AVG(d.score), 1) AS average_score,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r.ever_par30)
        / NULLIF(COUNT(r.application_id), 0), 2) AS par30_pct,
    MAX(a.occurred_at) AS latest_application_at
FROM warehouse.loan_applications a
LEFT JOIN latest_decision d USING (application_id)
LEFT JOIN repayment_by_application r USING (application_id);

CREATE OR REPLACE VIEW analytics.vw_country_performance AS
WITH latest_decision AS (
    SELECT DISTINCT ON (application_id)
        application_id, decision, score, approved_amount
    FROM warehouse.loan_decisions
    ORDER BY application_id, occurred_at DESC
), repayment_by_application AS (
    SELECT application_id, MAX(days_past_due) AS max_days_past_due
    FROM warehouse.repayments
    GROUP BY application_id
)
SELECT
    a.country_code,
    COUNT(DISTINCT a.customer_id) AS applicants,
    COUNT(*) AS applications,
    COUNT(*) FILTER (WHERE d.decision = 'approved') AS approvals,
    ROUND(100.0 * COUNT(*) FILTER (WHERE d.decision = 'approved')
        / NULLIF(COUNT(d.application_id), 0), 2) AS approval_rate_pct,
    COALESCE(SUM(d.approved_amount), 0) AS approved_value_local,
    ROUND(AVG(d.score), 1) AS average_credit_score,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r.max_days_past_due > 30)
        / NULLIF(COUNT(r.application_id), 0), 2) AS par30_pct
FROM warehouse.loan_applications a
LEFT JOIN latest_decision d USING (application_id)
LEFT JOIN repayment_by_application r USING (application_id)
GROUP BY a.country_code;

CREATE OR REPLACE VIEW analytics.vw_event_throughput AS
SELECT
    DATE_TRUNC('minute', ingested_at) AS minute,
    event_type,
    country_code,
    COUNT(*) AS event_count,
    ROUND(AVG(EXTRACT(EPOCH FROM (ingested_at - occurred_at)))::numeric, 3) AS avg_lag_seconds,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (
        ORDER BY EXTRACT(EPOCH FROM (ingested_at - occurred_at))
    )::numeric, 3) AS p95_lag_seconds
FROM warehouse.event_fact
WHERE ingested_at >= NOW() - INTERVAL '24 hours'
GROUP BY 1, 2, 3;
