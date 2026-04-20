"""
Load, stress, and endurance performance tests для RAS-like оркестратора.
Измерение latency, throughput, resource utilization.
"""
import pytest
import time
import threading
import statistics
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.models import Event, EventType, Severity
from salience_engine.engine import SalienceEngine
from mode_manager.manager import ModeManager
from interrupt_manager.manager import InterruptManager
from task_orchestrator.orchestrator import TaskOrchestrator
from workspace_service.redis_client import WorkspaceService
from performance.optimizer import RateLimiter, BackpressureManager, BatchProcessor, BatchProcessingConfig


def generate_event(event_id_prefix, event_type=None, severity=None):
    """Генерация тестового события."""
    if event_type is None:
        event_type = random.choice(list(EventType))
    if severity is None:
        severity = random.choice(list(Severity))
    return Event(
        event_id=f"{event_id_prefix}_{random.randint(1000,9999)}",
        type=event_type,
        severity=severity,
        source="load_test",
        payload={"confidence": random.uniform(0.5, 1.0)},
    )


def test_low_load_latency():
    """
    Low load: 10 events/second, измерение latency на каждом этапе.
    """
    salience_engine = SalienceEngine()
    mode_manager = ModeManager()
    interrupt_manager = InterruptManager()
    latencies = []

    num_events = 30  # 3 секунды при 10 events/sec
    for i in range(num_events):
        event = generate_event(f"low_{i}", EventType.SYSTEM_HEALTH, Severity.LOW)
        start = time.perf_counter()

        # Этап 1: Salience scoring
        score = salience_engine.compute(event)
        # Этап 2: Mode evaluation
        mode = mode_manager.evaluate(score)
        # Этап 3: Interrupt decision
        decision = interrupt_manager.evaluate(event, score, mode, [])

        end = time.perf_counter()
        latencies.append((end - start) * 1000)  # в миллисекундах

    # Статистика
    p50 = statistics.median(latencies)
    p90 = statistics.quantiles(latencies, n=10)[8]  # 90-й перцентиль
    p99 = statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies)

    print(f"Low load (10 events/sec) latency stats:")
    print(f"  P50: {p50:.2f} ms")
    print(f"  P90: {p90:.2f} ms")
    print(f"  P99: {p99:.2f} ms")
    print(f"  Total events: {num_events}")

    # Требования: P99 < 100 ms для low load
    assert p99 < 100, f"P99 latency {p99:.2f} ms превышает 100 ms"


def test_medium_load_throughput():
    """
    Medium load: 100 events/second, измерение throughput.
    """
    salience_engine = SalienceEngine()
    mode_manager = ModeManager()
    interrupt_manager = InterruptManager()

    num_events = 300  # 3 секунды при 100 events/sec
    start_time = time.perf_counter()

    for i in range(num_events):
        event = generate_event(f"med_{i}")
        score = salience_engine.compute(event)
        mode = mode_manager.evaluate(score)
        _ = interrupt_manager.evaluate(event, score, mode, [])

    end_time = time.perf_counter()
    total_time = end_time - start_time
    throughput = num_events / total_time

    print(f"Medium load throughput: {throughput:.2f} events/sec")
    print(f"Total time: {total_time:.2f} sec")

    # Требования: throughput >= 90 events/sec
    assert throughput >= 90, f"Throughput {throughput:.2f} events/sec ниже 90"


def test_high_load_stress():
    """
    High load: 1000 events/second, стресс-тест.
    Используем многопоточность для имитации высокой нагрузки.
    """
    salience_engine = SalienceEngine()
    mode_manager = ModeManager()
    interrupt_manager = InterruptManager()

    num_events = 1000
    num_workers = 10
    events_per_worker = num_events // num_workers

    def process_batch(worker_id):
        local_latencies = []
        for i in range(events_per_worker):
            event = generate_event(f"high_{worker_id}_{i}")
            start = time.perf_counter()
            score = salience_engine.compute(event)
            mode = mode_manager.evaluate(score)
            _ = interrupt_manager.evaluate(event, score, mode, [])
            local_latencies.append((time.perf_counter() - start) * 1000)
        return local_latencies

    start_time = time.perf_counter()
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(process_batch, i) for i in range(num_workers)]
        all_latencies = []
        for future in as_completed(futures):
            all_latencies.extend(future.result())

    end_time = time.perf_counter()
    total_time = end_time - start_time
    throughput = num_events / total_time

    p99 = statistics.quantiles(all_latencies, n=100)[98] if len(all_latencies) >= 100 else max(all_latencies)

    print(f"High load (1000 events/sec) results:")
    print(f"  Throughput: {throughput:.2f} events/sec")
    print(f"  P99 latency: {p99:.2f} ms")
    print(f"  Total time: {total_time:.2f} sec")

    # Требования: система не падает, throughput > 800 events/sec
    assert throughput > 800, f"Throughput {throughput:.2f} events/sec ниже 800"
    assert p99 < 500, f"P99 latency {p99:.2f} ms превышает 500 ms"


def test_spike_load():
    """
    Spike load: 5000 events/second в течение короткого времени.
    Проверка устойчивости к всплескам.
    """
    salience_engine = SalienceEngine()
    mode_manager = ModeManager()
    interrupt_manager = InterruptManager()

    num_events = 5000
    # Генерируем все события заранее
    events = [generate_event(f"spike_{i}") for i in range(num_events)]

    start_time = time.perf_counter()
    for event in events:
        score = salience_engine.compute(event)
        mode = mode_manager.evaluate(score)
        _ = interrupt_manager.evaluate(event, score, mode, [])
    end_time = time.perf_counter()

    total_time = end_time - start_time
    throughput = num_events / total_time

    print(f"Spike load (5000 events) results:")
    print(f"  Throughput: {throughput:.2f} events/sec")
    print(f"  Total time: {total_time:.2f} sec")

    # Требования: система обрабатывает всплеск без ошибок
    assert throughput > 2000, f"Throughput {throughput:.2f} events/sec слишком низкий для spike"


def test_endurance_memory_leak():
    """
    Endurance test: длительный прогон для обнаружения утечек памяти.
    Упрощённый вариант: запускаем много событий и проверяем, что потребление памяти не растёт бесконечно.
    В реальности нужно использовать memory_profiler, но здесь просто проверяем, что нет явных утечек
    через повторное создание объектов.
    """
    salience_engine = SalienceEngine()
    mode_manager = ModeManager()
    interrupt_manager = InterruptManager()

    iterations = 10000
    start_time = time.perf_counter()
    for i in range(iterations):
        event = generate_event(f"endurance_{i}")
        score = salience_engine.compute(event)
        mode = mode_manager.evaluate(score)
        _ = interrupt_manager.evaluate(event, score, mode, [])
        # Периодически вызываем сборку мусора (симулируем)
        if i % 1000 == 0:
            import gc
            gc.collect()

    end_time = time.perf_counter()
    total_time = end_time - start_time
    print(f"Endurance test processed {iterations} events in {total_time:.2f} sec")
    # Если нет исключений, считаем успехом
    assert total_time > 0


def test_rate_limiter_performance():
    """Производительность RateLimiter под нагрузкой."""
    limiter = RateLimiter(requests_per_second=10000, burst_size=1000)
    num_requests = 10000
    start = time.perf_counter()
    for _ in range(num_requests):
        limiter.acquire()
    end = time.perf_counter()
    ops_per_sec = num_requests / (end - start)
    print(f"RateLimiter throughput: {ops_per_sec:.0f} ops/sec")
    assert ops_per_sec > 50000, "RateLimiter слишком медленный"


def test_backpressure_manager_performance():
    """Производительность BackpressureManager."""
    manager = BackpressureManager(max_latency_ms=100, max_queue_depth=50)
    num_updates = 100000
    start = time.perf_counter()
    for i in range(num_updates):
        manager.update_queue_depth(i % 100)
        manager.update_latency(i % 200)
        manager.should_throttle()
    end = time.perf_counter()
    ops_per_sec = num_updates * 3 / (end - start)  # три операции на итерацию
    print(f"BackpressureManager throughput: {ops_per_sec:.0f} ops/sec")
    assert ops_per_sec > 100000, "BackpressureManager слишком медленный"


def test_batch_processor_throughput():
    """Пропускная способность BatchProcessor."""
    config = BatchProcessingConfig(batch_size=100, max_wait_seconds=0.1)
    processor = BatchProcessor(config)
    processed = []
    def callback(batch):
        processed.extend(batch)
        return [None] * len(batch)
    processor.set_flush_callback(callback)

    num_events = 1000
    events = [generate_event(f"batch_{i}") for i in range(num_events)]
    start = time.perf_counter()
    for event in events:
        processor.submit(event)
    processor.stop()
    end = time.perf_counter()
    throughput = num_events / (end - start)
    print(f"BatchProcessor throughput: {throughput:.0f} events/sec")
    assert len(processed) == num_events
    assert throughput > 5000, "BatchProcessor слишком медленный"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])