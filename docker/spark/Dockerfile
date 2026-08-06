FROM apache/spark:3.5.3

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/finpulse
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip3 install --no-cache-dir --break-system-packages .

USER 185
ENTRYPOINT ["/opt/spark/bin/spark-submit"]
CMD ["--master", "local[*]", "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3,org.apache.hadoop:hadoop-aws:3.3.4,org.postgresql:postgresql:42.7.4", "--conf", "spark.driver.memory=1g", "--conf", "spark.sql.shuffle.partitions=4", "/opt/finpulse/src/finpulse/streaming/spark_job.py"]

