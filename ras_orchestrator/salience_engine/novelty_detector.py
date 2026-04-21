"""
Novelty Detector – вычисление метрики новизны события на основе исторических паттернов.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from common.models import Event, HistoricalEvent
from .historical_repository import HistoricalRepository

logger = logging.getLogger(__name__)


class NoveltyDetector:
    """Детектор новизны событий."""

    def __init__(self, historical_repository: HistoricalRepository):
        self.historical_repository = historical_repository

    def compute_novelty(
        self,
        event: Event,
        history_window: timedelta = timedelta(days=7),
        algorithm: str = "frequency"
    ) -> float:
        """
        Возвращает оценку новизны от 0.0 (частое) до 1.0 (уникальное).

        Параметры:
            event: текущее событие
            history_window: период для анализа истории
            algorithm: алгоритм вычисления ('frequency', 'clustering', 'time_series')
        """
        # Получаем исторические события
        historical_events = self.historical_repository.get_events_in_window(
            event_type=event.type,
            source=event.source,
            window=history_window
        )

        if not historical_events:
            # Если нет истории, считаем событие новым (высокая новизна)
            return 0.9

        # Выбираем алгоритм
        if algorithm == "frequency":
            return self._frequency_based_novelty(event, historical_events)
        elif algorithm == "clustering":
            return self._clustering_based_novelty(event, historical_events)
        elif algorithm == "time_series":
            return self._time_series_novelty(event, historical_events)
        else:
            logger.warning(f"Unknown algorithm {algorithm}, falling back to frequency")
            return self._frequency_based_novelty(event, historical_events)

    def _frequency_based_novelty(self, event: Event, historical_events: List[HistoricalEvent]) -> float:
        """Новизна на основе частоты похожих событий."""
        # Простой подсчёт событий с тем же типом и источником
        similar_count = sum(
            1 for he in historical_events
            if he.type == event.type and he.source == event.source
        )
        total_count = len(historical_events)

        if total_count == 0:
            return 0.9

        # Частота = similar_count / total_count, нормализуем к новизне
        frequency = similar_count / total_count
        novelty = 1.0 - frequency
        # Применяем нелинейное преобразование для усиления редких событий
        novelty = novelty ** 0.5
        return max(0.0, min(1.0, novelty))

    def _clustering_based_novelty(self, event: Event, historical_events: List[HistoricalEvent]) -> float:
        """Новизна на основе кластеризации признаков (заглушка)."""
        # В реальной реализации здесь можно использовать scikit-learn для кластеризации
        # и вычислять расстояние до ближайшего кластера
        logger.debug("Clustering-based novelty not fully implemented, using frequency")
        return self._frequency_based_novelty(event, historical_events)

    def _time_series_novelty(self, event: Event, historical_events: List[HistoricalEvent]) -> float:
        """Новизна на основе временных паттернов (заглушка)."""
        # Анализ временных рядов: проверка, является ли событие выбросом по времени
        # Например, сравнение с сезонными паттернами
        logger.debug("Time-series novelty not fully implemented, using frequency")
        return self._frequency_based_novelty(event, historical_events)