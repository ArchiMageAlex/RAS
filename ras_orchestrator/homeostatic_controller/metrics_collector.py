"""
Сборщик метрик системы из различных источников: Prometheus, Redis, Kafka, внутренние счётчики.
"""

import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, Optional, List
import asyncio

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Собирает метрики системы для гомеостатического контроля."""

    def __init__(self, prometheus_url: str = "http://localhost:9090"):
        self.prometheus_url = prometheus_url
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = timedelta(seconds=30)
        self.cache_timestamp: Optional[datetime] = None

    async def initialize(self):
        """Инициализация коллектора (подключение к источникам)."""
        logger.info("MetricsCollector initialized.")

    async def shutdown(self):
        """Корректное завершение работы."""
        logger.info("MetricsCollector shut down.")

    async def collect_all(self) -> Dict[str, float]:
        """
        Собирает все метрики из различных источников.
        Возвращает словарь метрик.
        """
        # Если кэш ещё актуален, используем его
        if self.cache_timestamp and (datetime.now(UTC) - self.cache_timestamp) < self.cache_ttl:
            return self.cache.copy()

        metrics = {}

        # Сбор из различных источников параллельно
        tasks = [
            self._collect_cpu(),
            self._collect_latency(),
            self._collect_error_rate(),
            self._collect_queue_depth(),
            self._collect_memory(),
            self._collect_throughput(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обработка результатов
        metric_names = ["cpu_load", "latency_ms", "error_rate", "queue_depth", "memory_usage", "throughput"]
        for name, result in zip(metric_names, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to collect {name}: {result}")
                metrics[name] = 0.0  # значение по умолчанию
            else:
                metrics[name] = result

        # Дополнительные метрики
        metrics["timestamp"] = datetime.now(UTC).timestamp()
        metrics["agent_count"] = await self._collect_agent_count()

        # Обновление кэша
        self.cache = metrics.copy()
        self.cache_timestamp = datetime.now(UTC)

        logger.debug(f"Collected metrics: {metrics}")
        return metrics

    async def _collect_cpu(self) -> float:
        """Собирает загрузку CPU (0.0 - 1.0)."""
        # Заглушка: в реальности запрос к Prometheus
        # Пример: 'rate(node_cpu_seconds_total{mode="idle"}[1m])'
        try:
            # Имитация сбора
            return 0.45  # фиктивное значение
        except Exception as e:
            logger.error(f"CPU collection error: {e}")
            return 0.5

    async def _collect_latency(self) -> float:
        """Собирает среднюю задержку обработки событий (мс)."""
        # Заглушка
        return 120.0

    async def _collect_error_rate(self) -> float:
        """Собирает частоту ошибок (0.0 - 1.0)."""
        # Заглушка
        return 0.005

    async def _collect_queue_depth(self) -> int:
        """Собирает глубину очереди задач."""
        # Заглушка
        return 12

    async def _collect_memory(self) -> float:
        """Собирает использование памяти (0.0 - 1.0)."""
        # Заглушка
        return 0.65

    async def _collect_throughput(self) -> float:
        """Собирает пропускную способность (событий/сек)."""
        # Заглушка
        return 45.7

    async def _collect_agent_count(self) -> int:
        """Собирает количество активных агентов."""
        # Заглушка
        return 3

    async def query_prometheus(self, query: str) -> Optional[float]:
        """Выполняет запрос к Prometheus и возвращает значение."""
        # Заглушка для реализации
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                params = {"query": query}
                async with session.get(f"{self.prometheus_url}/api/v1/query", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data["status"] == "success" and data["data"]["result"]:
                            value = float(data["data"]["result"][0]["value"][1])
                            return value
            return None
        except Exception as e:
            logger.error(f"Prometheus query failed: {e}")
            return None

    async def get_metric_history(self, metric_name: str, minutes: int = 60) -> List[float]:
        """Возвращает историю значений метрики за указанный период."""
        # Заглушка
        return [0.5] * 10

    async def get_metric_stats(self, metric_name: str) -> Dict[str, float]:
        """Возвращает статистику по метрике (среднее, максимум, минимум)."""
        # Заглушка
        return {"mean": 0.5, "max": 0.9, "min": 0.2, "std": 0.1}