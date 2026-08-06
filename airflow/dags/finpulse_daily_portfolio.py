from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator
from airflow.providers.common.sql.operators.sql import (
    SQLCheckOperator,
    SQLExecuteQueryOperator,
)

DEFAULT_ARGS = {
    "owner": "data-platform",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
}


@dag(
    dag_id="finpulse_daily_portfolio",
    description="Curate credit portfolio marts and enforce data product quality gates",
    schedule="15 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["fintech", "portfolio", "dbt", "quality"],
)
def daily_portfolio():
    streaming_freshness = SQLCheckOperator(
        task_id="check_streaming_freshness",
        conn_id="finpulse_warehouse",
        sql="""
            SELECT COALESCE(MAX(ingested_at) > NOW() - INTERVAL '60 minutes', FALSE)
            FROM warehouse.event_fact
        """,
    )

    source_volume = SQLCheckOperator(
        task_id="check_source_volume",
        conn_id="finpulse_warehouse",
        sql="""
            SELECT COUNT(*) >= 10
            FROM warehouse.event_fact
            WHERE processing_date >= CURRENT_DATE - 1
        """,
    )

    dbt_run = BashOperator(
        task_id="build_warehouse_marts",
        bash_command="cd /opt/airflow/dbt && dbt run --profiles-dir . --target dev",
    )
    dbt_test = BashOperator(
        task_id="test_warehouse_marts",
        bash_command="cd /opt/airflow/dbt && dbt test --profiles-dir . --target dev",
    )

    @task
    def quality_manifest(**context):
        return {
            "data_interval_start": context["data_interval_start"].isoformat(),
            "data_interval_end": context["data_interval_end"].isoformat(),
            "checks": ["streaming_freshness", "source_volume", "dbt_tests"],
            "status": "passed",
        }

    publish_audit = SQLExecuteQueryOperator(
        task_id="publish_pipeline_audit",
        conn_id="finpulse_warehouse",
        sql="""
            INSERT INTO observability.pipeline_runs (
                pipeline_name, started_at, completed_at, status, metadata
            ) VALUES (
                'finpulse_daily_portfolio',
                '{{ data_interval_start }}'::timestamptz,
                NOW(),
                'success',
                '{{ ti.xcom_pull(task_ids="quality_manifest") | tojson }}'::jsonb
            )
        """,
    )
    analyze_tables = SQLExecuteQueryOperator(
        task_id="analyze_marts",
        conn_id="finpulse_warehouse",
        sql="ANALYZE analytics.fct_credit_portfolio; ANALYZE analytics.dim_customer_features;",
        autocommit=True,
    )

    manifest = quality_manifest()
    [streaming_freshness, source_volume] >> dbt_run >> dbt_test >> manifest
    manifest >> publish_audit >> analyze_tables


daily_portfolio()
