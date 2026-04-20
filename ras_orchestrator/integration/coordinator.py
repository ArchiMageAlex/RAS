"""
Координатор интеграции между компонентами.
Обеспечивает retry logic, idempotency keys, dead letter queues.
"""
import json
import logging
import uuid
import time
from typing import Any, Dict, Optional, Callable, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import redis

from common.models import Event

logger = logging.getLogger(__name__)


class OperationStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class IdempotencyRecord:
    """Запись идемпотентности для операции."""
    key: str
    result: Optional[Dict[str, Any]]
    status: OperationStatus
    created_at: datetime
    updated_at: datetime


class IdempotencyStore:
    """Хранилище идемпотентных ключей (на основе Redis)."""

    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 3600):
        self.redis = redis_client
        self.ttl = ttl_seconds
        self.prefix = "idempotency:"

    def _make_key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def store(self, key: str, result: Dict[str, Any], status: OperationStatus):
        """Сохраняет результат операции."""
        record = IdempotencyRecord(
            key=key,
            result=result,
            status=status,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        data = json.dumps({
            "result": record.result,
            "status": record.status.value,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        })
        self.redis.setex(self._make_key(key), self.ttl, data)

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        """Получает запись по ключу."""
        data = self.redis.get(self._make_key(key))
        if not data:
            return None
        obj = json.loads(data)
        return IdempotencyRecord(
            key=key,
            result=obj["result"],
            status=OperationStatus(obj["status"]),
            created_at=datetime.fromisoformat(obj["created_at"]),
            updated_at=datetime.fromisoformat(obj["updated_at"]),
        )

    def exists(self, key: str) -> bool:
        """Проверяет, существует ли ключ."""
        return self.redis.exists(self._make_key(key)) == 1


class RetryPolicy:
    """Политика повторных попыток."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 30.0,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay

    def get_delay(self, attempt: int) -> float:
        """Вычисляет задержку перед повторной попыткой."""
        if attempt <= 0:
            return 0.0
        delay = self.initial_delay * (self.backoff_factor ** (attempt - 1))
        return min(delay, self.max_delay)


class DeadLetterQueue:
    """Очередь мёртвых писем (DLQ) для хранения неудачных операций."""

    def __init__(self, redis_client: redis.Redis, queue_name: str = "dlq"):
        self.redis = redis_client
        self.queue_name = f"dlq:{queue_name}"

    def push(self, error: Dict[str, Any]):
        """Добавляет ошибку в DLQ."""
        self.redis.lpush(self.queue_name, json.dumps(error))
        logger.warning(f"Message pushed to DLQ: {error.get('error_type')}")

    def pop(self) -> Optional[Dict[str, Any]]:
        """Извлекает ошибку из DLQ (для обработки)."""
        data = self.redis.rpop(self.queue_name)
        if data:
            return json.loads(data)
        return None

    def size(self) -> int:
        """Возвращает размер DLQ."""
        return self.redis.llen(self.queue_name)


class IntegrationCoordinator:
    """
    Координатор интеграции, обеспечивающий:
    - Retry logic с экспоненциальной отсрочкой
    - Idempotency keys для предотвращения дублирования
    - Dead letter queues для обработки ошибок
    - Согласованное взаимодействие через event bus
    """

    def __init__(
        self,
        kafka_bootstrap_servers: str = "localhost:9092",
        redis_host: str = "localhost",
        redis_port: int = 6379,
    ):
        # Kafka producer для отправки событий
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=3,
        )
        # Redis для idempotency и DLQ
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.idempotency_store = IdempotencyStore(self.redis)
        self.dlq = DeadLetterQueue(self.redis)
        self.retry_policy = RetryPolicy()

    def send_event_with_idempotency(
        self,
        event: Event,
        idempotency_key: Optional[str] = None,
        topic: str = "ras_events",
    ) -> Dict[str, Any]:
        """
        Отправляет событие с поддержкой идемпотентности.
        Если операция с таким ключом уже выполнена, возвращает сохранённый результат.
        """
        key = idempotency_key or str(uuid.uuid4())
        # Проверяем, не выполнялась ли уже операция
        existing = self.idempotency_store.get(key)
        if existing and existing.status == OperationStatus.SUCCESS:
            logger.info(f"Idempotency hit for key {key}, returning cached result.")
            return {"status": "cached", "result": existing.result}

        # Выполняем операцию с retry logic
        result = self._send_with_retry(event, topic, key)

        # Сохраняем результат
        self.idempotency_store.store(key, result, OperationStatus.SUCCESS)
        return result

    def _send_with_retry(self, event: Event, topic: str, idempotency_key: str) -> Dict[str, Any]:
        """Отправляет событие с повторными попытками."""
        last_error = None
        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                if attempt > 0:
                    delay = self.retry_policy.get_delay(attempt)
                    logger.info(f"Retry {attempt} for event {event.event_id} after {delay}s")
                    time.sleep(delay)

                future = self.producer.send(topic, event.model_dump())
                record_metadata = future.get(timeout=10)
                result = {
                    "success": True,
                    "partition": record_metadata.partition,
                    "offset": record_metadata.offset,
                    "event_id": event.event_id,
                }
                logger.debug(f"Event sent successfully: {event.event_id}")
                return result
            except KafkaError as e:
                last_error = e
                logger.warning(f"Attempt {attempt} failed for event {event.event_id}: {e}")
                if attempt == self.retry_policy.max_retries:
                    break

        # Все попытки исчерпаны -> отправляем в DLQ
        dlq_entry = {
            "event": event.model_dump(),
            "error_type": type(last_error).__name__,
            "error_message": str(last_error),
            "idempotency_key": idempotency_key,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.dlq.push(dlq_entry)
        return {
            "success": False,
            "error": "All retries exhausted, moved to DLQ",
            "dlq_entry": dlq_entry,
        }

    def process_dlq(self, handler: Callable[[Dict[str, Any]], bool]):
        """
        Обрабатывает сообщения из DLQ с помощью переданного обработчика.
        Если обработчик возвращает True, сообщение удаляется из DLQ.
        """
        while True:
            entry = self.dlq.pop()
            if not entry:
                break
            logger.info(f"Processing DLQ entry: {entry.get('event_id')}")
            try:
                success = handler(entry)
                if success:
                    logger.info(f"DLQ entry processed successfully, removed.")
                else:
                    # Возвращаем обратно в DLQ для последующей обработки
                    self.dlq.push(entry)
                    logger.warning(f"Handler failed, re-queued DLQ entry.")
            except Exception as e:
                logger.error(f"Error processing DLQ entry: {e}")
                self.dlq.push(entry)  # возвращаем обратно

    def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья координатора."""
        kafka_ok = False
        try:
            self.producer.partitions_for("ras_events")
            kafka_ok = True
        except Exception as e:
            logger.error(f"Kafka health check failed: {e}")

        redis_ok = self.redis.ping()

        return {
            "kafka": kafka_ok,
            "redis": redis_ok,
            "dlq_size": self.dlq.size(),
        }


# Глобальный экземпляр
coordinator = IntegrationCoordinator()


def get_integration_coordinator() -> IntegrationCoordinator:
    return coordinator