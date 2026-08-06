FROM apache/airflow:2.10.4-python3.11

USER airflow
RUN pip install --no-cache-dir \
    apache-airflow-providers-postgres==5.13.1 \
    apache-airflow-providers-apache-spark==4.11.3 \
    dbt-postgres==1.8.2

