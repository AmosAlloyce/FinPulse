from __future__ import annotations

import json
import logging
import signal
import time
from collections.abc import Callable
from threading import Event

from confluent_kafka import KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from finpulse.config import get_settings
from finpulse.generator import SyntheticEventGenerator
from finpulse.logging import configure_logging

LOGGER = logging.getLogger(__name__)


def ensure_topics(bootstrap_servers: str, topics: list[str]) -> None:
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    futures = admin.create_topics(
        [NewTopic(topic, num_partitions=6, replication_factor=1) for topic in topics]
    )
    for topic, future in futures.items():
        try:
            future.result()
            LOGGER.info("created Kafka topic", extra={"topic": topic})
        except KafkaException as exc:
            if "TOPIC_ALREADY_EXISTS" not in str(exc):
                raise


def delivery_callback(error: object, message: object) -> None:
    if error:
        LOGGER.error("event delivery failed", extra={"error": str(error)})


def produce_forever(on_event: Callable[[str], None] | None = None) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    ensure_topics(
        settings.kafka_bootstrap_servers,
        [settings.kafka_raw_topic, settings.kafka_dlq_topic],
    )
    producer = Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "client.id": "finpulse-synthetic-ingress",
            "enable.idempotence": True,
            "acks": "all",
            "compression.type": "snappy",
            "linger.ms": 20,
            "batch.size": 131_072,
        }
    )
    generator = SyntheticEventGenerator(settings.random_seed, settings.countries)
    interval = 1 / max(0.1, settings.demo_event_rate)
    sent = 0

    LOGGER.info(
        "producer started",
        extra={"topic": settings.kafka_raw_topic, "events_per_second": settings.demo_event_rate},
    )
    while not stop.is_set():
        event = generator.next_event()
        payload = event.to_json()
        try:
            producer.produce(
                settings.kafka_raw_topic,
                key=str(event.customer_id),
                value=payload,
                headers={"schema_version": event.schema_version, "trace_id": event.trace_id},
                on_delivery=delivery_callback,
            )
            # Deliberately inject a tiny number of malformed messages to exercise the DLQ path.
            if sent > 0 and sent % 500 == 0:
                producer.produce(
                    settings.kafka_raw_topic,
                    key="quality-test",
                    value=json.dumps({"schema_version": "0.0", "malformed": True}),
                    on_delivery=delivery_callback,
                )
            producer.poll(0)
            if on_event:
                on_event(payload)
            sent += 1
            if sent % 100 == 0:
                LOGGER.info("events produced", extra={"event_count": sent})
        except BufferError:
            LOGGER.warning("producer queue full; applying backpressure")
            producer.poll(1)
        time.sleep(interval)

    remaining = producer.flush(15)
    LOGGER.info("producer stopped", extra={"event_count": sent, "undelivered": remaining})


def main() -> None:
    produce_forever()


if __name__ == "__main__":
    main()
