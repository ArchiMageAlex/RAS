"""
Integration tests для координатора и взаимодействия компонентов.
"""
import pytest
import time
from unittest.mock import Mock, patch
from common.models import Event, EventType, Severity
from integration.coordinator import (
    IntegrationCoordinator,
    IdempotencyStore,
    RetryPolicy,
    DeadLetterQueue,
    OperationStatus,
)


def test_idempotency_store():
    """Тест хранилища идемпотентности."""
    import redis
    mock_redis = Mock(spec=redis.Redis)
    store = IdempotencyStore(mock_redis, ttl_seconds=10)
    key = "test-key"
    result = {"success": True}
    # Сохраняем
    store.store(key, result, OperationStatus.SUCCESS)
    # Проверяем, что redis.setex был вызван
    assert mock_redis.setex.called
    # Получаем
    mock_redis.get.return_value = '{"result": {"success": true}, "status": "success", "created_at": "2024-01-01T00:00:00", "updated_at": "2024-01-01T00:00:00"}'
    record = store.get(key)
    assert record is not None
    assert record.status == OperationStatus.SUCCESS
    assert record.result == {"success": True}


def test_retry_policy():
    """Тест политики повторных попыток."""
    policy = RetryPolicy(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    assert policy.get_delay(1) == 1.0
    assert policy.get_delay(2) == 2.0
    assert policy.get_delay(3) == 4.0
    assert policy.get_delay(4) == 8.0
    # Проверка ограничения max_delay
    policy2 = RetryPolicy(max_delay=5.0)
    assert policy2.get_delay(10) <= 5.0


def test_dead_letter_queue():
    """Тест очереди мёртвых писем."""
    import redis
    mock_redis = Mock(spec=redis.Redis)
    dlq = DeadLetterQueue(mock_redis, "test")
    error = {"error": "test"}
    dlq.push(error)
    assert mock_redis.lpush.called
    # Извлечение
    mock_redis.rpop.return_value = '{"error": "test"}'
    entry = dlq.pop()
    assert entry == error


@patch('integration.coordinator.KafkaProducer')
def test_send_event_with_idempotency(mock_producer_class):
    """Тест отправки события с идемпотентностью."""
    mock_producer = Mock()
    mock_producer_class.return_value = mock_producer
    mock_future = Mock()
    mock_future.get.return_value = Mock(partition=0, offset=123)
    mock_producer.send.return_value = mock_future

    coordinator = IntegrationCoordinator()
    coordinator.redis = Mock()
    coordinator.redis.get.return_value = None  # нет кэша

    event = Event(
        event_id="test-1",
        type=EventType.SYSTEM_HEALTH,
        severity=Severity.LOW,
        source="test",
    )
    result = coordinator.send_event_with_idempotency(event, idempotency_key="key1")
    assert result["success"] is True
    assert result["partition"] == 0
    assert result["offset"] == 123
    # Проверяем, что producer.send был вызван
    assert mock_producer.send.called


@patch('integration.coordinator.KafkaProducer')
def test_send_event_idempotency_hit(mock_producer_class):
    """Тест попадания в идемпотентность (повторная отправка)."""
    mock_producer = Mock()
    mock_producer_class.return_value = mock_producer
    coordinator = IntegrationCoordinator()
    # Эмулируем, что операция уже выполнена
    coordinator.idempotency_store.get = Mock(return_value=Mock(
        status=OperationStatus.SUCCESS,
        result={"success": True, "partition": 0, "offset": 999},
    ))
    event = Event(
        event_id="test-2",
        type=EventType.SYSTEM_HEALTH,
        severity=Severity.LOW,
        source="test",
    )
    result = coordinator.send_event_with_idempotency(event, idempotency_key="key2")
    assert result["status"] == "cached"
    assert result["result"]["offset"] == 999
    # Producer.send не должен вызываться
    assert not mock_producer.send.called


def test_health_check():
    """Тест проверки здоровья."""
    coordinator = IntegrationCoordinator()
    coordinator.producer = Mock()
    coordinator.producer.partitions_for.return_value = [0]
    coordinator.redis = Mock()
    coordinator.redis.ping.return_value = True
    coordinator.dlq.size = Mock(return_value=5)

    health = coordinator.health_check()
    assert health["kafka"] is True
    assert health["redis"] is True
    assert health["dlq_size"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])