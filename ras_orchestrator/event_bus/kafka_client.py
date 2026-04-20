import json
import logging
from typing import Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError

from common.models import Event

logger = logging.getLogger(__name__)

# Конфигурация Kafka (заглушка, будет переопределена через переменные окружения)
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
EVENT_TOPIC = "ras_events"

_producer: Optional[KafkaProducer] = None


def get_producer():
    global _producer
    if _producer is None:
        try:
            _producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )
            logger.info(f"Kafka producer connected to {KAFKA_BOOTSTRAP_SERVERS}")
        except Exception as e:
            logger.error(f"Failed to create Kafka producer: {e}")
            raise
    return _producer


async def produce_event(event: Event):
    """Асинхронно отправляет событие в Kafka."""
    producer = get_producer()
    try:
        event_dict = event.model_dump()
        future = producer.send(EVENT_TOPIC, event_dict)
        # Блокируем для простоты (в реальности можно использовать callback)
        result = future.get(timeout=10)
        logger.debug(f"Event sent to partition {result.partition} offset {result.offset}")
        return True
    except KafkaError as e:
        logger.error(f"Kafka error while sending event: {e}")
        return False


def close_producer():
    global _producer
    if _producer:
        _producer.close()
        _producer = None
        logger.info("Kafka producer closed.")