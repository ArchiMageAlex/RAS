"""
Performance tests для оптимизаций.
"""
import pytest
import time
import threading
from performance.optimizer import (
    BatchProcessor,
    BatchProcessingConfig,
    RateLimiter,
    BackpressureManager,
    HorizontalScalingManager,
)
from common.models import Event, EventType, Severity


def test_batch_processor():
    """Тест batch processor."""
    config = BatchProcessingConfig(batch_size=3, max_wait_seconds=0.5)
    processor = BatchProcessor(config)
    processed = []

    def callback(batch):
        processed.extend(batch)
        return [None] * len(batch)

    processor.set_flush_callback(callback)

    events = [
        Event(event_id=f"e{i}", type=EventType.SYSTEM_HEALTH, severity=Severity.LOW, source="test")
        for i in range(5)
    ]
    for e in events:
        processor.submit(e)

    # Ждём, пока батч обработается
    time.sleep(1.0)
    processor.stop()
    # Должны обработаться все события (возможно, два батча)
    assert len(processed) == 5


def test_rate_limiter():
    """Тест ограничителя скорости."""
    limiter = RateLimiter(requests_per_second=10, burst_size=5)
    # Первые 5 запросов должны проходить (burst)
    for _ in range(5):
        assert limiter.acquire() is True
    # Шестой запрос должен быть отклонён (rate limit)
    assert limiter.acquire() is False
    # Ждём 0.2 секунды, чтобы накопились токены
    time.sleep(0.2)
    assert limiter.acquire() is True  # теперь должен пройти


def test_backpressure_manager():
    """Тест менеджера обратного давления."""
    manager = BackpressureManager(max_latency_ms=100, max_queue_depth=50)
    manager.update_queue_depth(10)
    assert manager.should_throttle() is False
    manager.update_queue_depth(60)
    assert manager.should_throttle() is True
    manager.update_queue_depth(10)
    manager.update_latency(150)
    assert manager.should_throttle() is True
    manager.update_latency(50)
    assert manager.should_throttle() is False


def test_backpressure_throttle_factor():
    """Тест коэффициента throttling."""
    manager = BackpressureManager(max_latency_ms=100, max_queue_depth=50)
    manager.update_queue_depth(75)  # превышение на 25
    factor = manager.get_throttle_factor()
    # (75-50)/50 = 0.5
    assert 0.49 < factor < 0.51
    manager.update_queue_depth(30)
    manager.update_latency(120)  # превышение latency на 20
    factor = manager.get_throttle_factor()
    # (120-100)/100 = 0.2
    assert 0.19 < factor < 0.21


def test_horizontal_scaling_manager():
    """Тест менеджера горизонтального масштабирования."""
    manager = HorizontalScalingManager(
        min_instances=1,
        max_instances=5,
        scale_out_threshold=0.8,
        scale_in_threshold=0.2,
    )
    # Низкая нагрузка
    manager.update_metrics(cpu=0.1, memory=0.3, queue_depth=5, latency_ms=50)
    action = manager.evaluate_scaling()
    assert action is None
    # Высокая нагрузка
    manager.update_metrics(cpu=0.9, memory=0.8, queue_depth=1500, latency_ms=1200)
    action = manager.evaluate_scaling()
    assert action == "scale_out"
    manager.apply_scaling(action)
    assert manager.current_instances == 2
    # Снова низкая нагрузка после масштабирования
    manager.update_metrics(cpu=0.1, memory=0.2, queue_depth=10, latency_ms=30)
    action = manager.evaluate_scaling()
    assert action == "scale_in"
    manager.apply_scaling(action)
    assert manager.current_instances == 1


def test_concurrent_rate_limiter():
    """Тест rate limiter в многопоточном режиме."""
    limiter = RateLimiter(requests_per_second=100, burst_size=20)
    results = []
    def worker():
        results.append(limiter.acquire())

    threads = [threading.Thread(target=worker) for _ in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Только 20 запросов должны пройти (burst)
    assert sum(results) == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])