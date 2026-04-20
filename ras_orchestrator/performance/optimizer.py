"""
Оптимизации производительности и масштабируемости:
- batch processing
- rate limiting
- backpressure handling
- горизонтальное масштабирование
"""
import asyncio
import time
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import threading
from queue import Queue, Full, Empty

from common.models import Event, SalienceScore
from salience_engine.engine import get_salience_engine

logger = logging.getLogger(__name__)


@dataclass
class BatchProcessingConfig:
    """Конфигурация batch processing."""
    batch_size: int = 100
    max_wait_seconds: float = 1.0
    max_queue_size: int = 10000


class BatchProcessor:
    """
    Обработчик событий батчами для снижения нагрузки и увеличения пропускной способности.
    """

    def __init__(self, config: BatchProcessingConfig):
        self.config = config
        self.queue: Queue = Queue(maxsize=config.max_queue_size)
        self.batch: List[Event] = []
        self.last_flush = time.time()
        self.lock = threading.Lock()
        self.flush_callback: Optional[Callable[[List[Event]], List[SalienceScore]]] = None
        self._stop = False
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def set_flush_callback(self, callback: Callable[[List[Event]], List[SalienceScore]]):
        """Устанавливает функцию обработки батча."""
        self.flush_callback = callback

    def submit(self, event: Event) -> bool:
        """
        Добавляет событие в очередь на обработку.
        Возвращает True, если событие принято, False если очередь переполнена.
        """
        try:
            self.queue.put_nowait(event)
            return True
        except Full:
            logger.warning("Batch processor queue full, event dropped.")
            return False

    def _worker(self):
        """Рабочий поток, собирающий события в батчи и обрабатывающий их."""
        while not self._stop:
            try:
                # Ждём событие с таймаутом, чтобы периодически флашить
                event = self.queue.get(timeout=self.config.max_wait_seconds)
                with self.lock:
                    self.batch.append(event)
                    if len(self.batch) >= self.config.batch_size:
                        self._flush_batch()
                    elif time.time() - self.last_flush > self.config.max_wait_seconds:
                        self._flush_batch()
            except Empty:
                # Таймаут, проверяем нужно ли флашить
                with self.lock:
                    if self.batch and time.time() - self.last_flush > self.config.max_wait_seconds:
                        self._flush_batch()
            except Exception as e:
                logger.error(f"Batch processor worker error: {e}")

    def _flush_batch(self):
        """Обрабатывает текущий батч."""
        if not self.batch:
            return
        batch_to_process = self.batch.copy()
        self.batch.clear()
        self.last_flush = time.time()

        if self.flush_callback:
            try:
                results = self.flush_callback(batch_to_process)
                logger.info(f"Batch processed: {len(batch_to_process)} events, {len(results)} scores")
            except Exception as e:
                logger.error(f"Batch processing failed: {e}")
        else:
            logger.warning("No flush callback set, batch discarded.")

    def stop(self):
        """Останавливает процессор и обрабатывает оставшиеся события."""
        self._stop = True
        self._thread.join(timeout=5)
        with self.lock:
            if self.batch:
                self._flush_batch()


class RateLimiter:
    """
    Ограничитель скорости (rate limiter) на основе токенов.
    Поддерживает разные лимиты для разных типов событий.
    """

    def __init__(self, requests_per_second: float = 100, burst_size: int = 10):
        self.rate = requests_per_second
        self.burst = burst_size
        self.tokens = burst_size
        self.last_update = time.time()
        self.lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> bool:
        """
        Пытается получить указанное количество токенов.
        Возвращает True, если токены доступны, иначе False.
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            # Пополняем токены в соответствии с rate
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def acquire_async(self, tokens: int = 1) -> bool:
        """Асинхронная версия acquire."""
        return self.acquire(tokens)


class BackpressureManager:
    """
    Менеджер обратного давления (backpressure) для контроля перегрузки.
    Использует скользящее окно для мониторинга latency и queue depth.
    """

    def __init__(self, max_latency_ms: float = 1000, max_queue_depth: int = 1000):
        self.max_latency = max_latency_ms
        self.max_queue_depth = max_queue_depth
        self.latency_history: List[float] = []
        self.window_size = 100
        self.queue_depth = 0

    def update_latency(self, latency_ms: float):
        """Обновляет историю latency."""
        self.latency_history.append(latency_ms)
        if len(self.latency_history) > self.window_size:
            self.latency_history.pop(0)

    def update_queue_depth(self, depth: int):
        """Обновляет глубину очереди."""
        self.queue_depth = depth

    def should_throttle(self) -> bool:
        """
        Определяет, нужно ли применять throttling.
        Возвращает True, если система перегружена.
        """
        if self.queue_depth > self.max_queue_depth:
            return True
        if self.latency_history:
            avg_latency = sum(self.latency_history) / len(self.latency_history)
            if avg_latency > self.max_latency:
                return True
        return False

    def get_throttle_factor(self) -> float:
        """
        Возвращает коэффициент throttling (0.0 - 1.0),
        где 1.0 означает полную остановку, 0.0 - нет throttling.
        """
        factor = 0.0
        if self.queue_depth > self.max_queue_depth:
            factor = min(1.0, (self.queue_depth - self.max_queue_depth) / self.max_queue_depth)
        if self.latency_history:
            avg_latency = sum(self.latency_history) / len(self.latency_history)
            if avg_latency > self.max_latency:
                factor = max(factor, min(1.0, (avg_latency - self.max_latency) / self.max_latency))
        return factor


class HorizontalScalingManager:
    """
    Менеджер горизонтального масштабирования.
    Мониторит метрики и принимает решения о масштабировании (scale out/in).
    """

    def __init__(
        self,
        min_instances: int = 1,
        max_instances: int = 10,
        scale_out_threshold: float = 0.8,
        scale_in_threshold: float = 0.2,
    ):
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.scale_out_threshold = scale_out_threshold
        self.scale_in_threshold = scale_in_threshold
        self.current_instances = min_instances
        self.metrics_history: List[Dict[str, float]] = []

    def update_metrics(self, cpu: float, memory: float, queue_depth: int, latency_ms: float):
        """Обновляет метрики для принятия решений."""
        self.metrics_history.append({
            "cpu": cpu,
            "memory": memory,
            "queue_depth": queue_depth,
            "latency_ms": latency_ms,
            "timestamp": time.time(),
        })
        # Ограничиваем размер истории
        if len(self.metrics_history) > 100:
            self.metrics_history.pop(0)

    def evaluate_scaling(self) -> Optional[str]:
        """
        Оценивает необходимость масштабирования.
        Возвращает 'scale_out', 'scale_in' или None.
        """
        if not self.metrics_history:
            return None

        # Используем последние метрики
        last = self.metrics_history[-1]
        cpu = last["cpu"]
        queue_depth = last["queue_depth"]
        latency = last["latency_ms"]

        # Эвристика: если нагрузка высокая и есть задержки, scale out
        if (cpu > self.scale_out_threshold or queue_depth > 1000 or latency > 1000) \
                and self.current_instances < self.max_instances:
            return "scale_out"
        # Если нагрузка низкая и инстансов больше минимума, scale in
        if cpu < self.scale_in_threshold and queue_depth < 100 and latency < 100 \
                and self.current_instances > self.min_instances:
            return "scale_in"
        return None

    def apply_scaling(self, action: str):
        """Применяет scaling (заглушка, в реальности вызывает оркестратор)."""
        if action == "scale_out" and self.current_instances < self.max_instances:
            self.current_instances += 1
            logger.info(f"Scaling out to {self.current_instances} instances")
        elif action == "scale_in" and self.current_instances > self.min_instances:
            self.current_instances -= 1
            logger.info(f"Scaling in to {self.current_instances} instances")


# Глобальные экземпляры
batch_processor = BatchProcessor(BatchProcessingConfig())
rate_limiter = RateLimiter(requests_per_second=1000)
backpressure_manager = BackpressureManager()
scaling_manager = HorizontalScalingManager()


def get_batch_processor() -> BatchProcessor:
    return batch_processor


def get_rate_limiter() -> RateLimiter:
    return rate_limiter


def get_backpressure_manager() -> BackpressureManager:
    return backpressure_manager


def get_scaling_manager() -> HorizontalScalingManager:
    return scaling_manager