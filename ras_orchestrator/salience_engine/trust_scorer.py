"""
Trust Scorer – оценка доверия к источнику события на основе исторической точности, репутации и консистентности.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from common.models import Event, SourceTrust

logger = logging.getLogger(__name__)


class TrustScorer:
    """Вычисление trust score для источников событий."""

    def __init__(self, source_registry: 'SourceRegistry'):
        self.source_registry = source_registry

    def compute_trust(
        self,
        source: str,
        event: Optional[Event] = None,
        ground_truth: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Возвращает оценку доверия к источнику от 0.0 (недоверенный) до 1.0 (доверенный).

        Параметры:
            source: идентификатор источника
            event: текущее событие (опционально, для контекста)
            ground_truth: данные для проверки точности (опционально)
        """
        # Получаем или создаём запись об источнике
        source_trust = self.source_registry.get_or_create(source)

        # Если есть ground truth, обновляем точность
        if ground_truth is not None:
            self._update_accuracy(source_trust, event, ground_truth)

        # Вычисляем итоговый trust score
        trust = self._compute_final_score(source_trust)
        return trust

    def _update_accuracy(
        self,
        source_trust: SourceTrust,
        event: Optional[Event],
        ground_truth: Dict[str, Any]
    ) -> None:
        """Обновляет метрику точности источника на основе ground truth."""
        # В реальной реализации здесь можно сравнить предсказания источника с фактическими данными
        # Пока что просто увеличиваем счётчик событий и слегка корректируем accuracy
        source_trust.events_count += 1
        # Заглушка: предполагаем, что источник прав в 90% случаев
        # В реальности нужно вычислять на основе сравнения payload с ground_truth
        correct = True  # временно
        if correct:
            # Обновляем accuracy с экспоненциальным скользящим средним
            alpha = 0.1
            source_trust.accuracy = (1 - alpha) * source_trust.accuracy + alpha * 1.0
        else:
            alpha = 0.2
            source_trust.accuracy = (1 - alpha) * source_trust.accuracy + alpha * 0.0

        source_trust.last_updated = datetime.utcnow()
        self.source_registry.save(source_trust)

    def _compute_final_score(self, source_trust: SourceTrust) -> float:
        """Вычисляет итоговый trust score на основе метрик источника."""
        # Если источник не имеет событий, возвращаем дефолтный низкий trust
        if source_trust.events_count == 0:
            return 0.3

        # Базовый trust score – это accuracy
        base = source_trust.accuracy

        # Корректировка на количество событий: больше событий → больше доверия
        count_factor = min(1.0, source_trust.events_count / 100.0)
        # Корректировка на время: недавно обновлённые источники получают бонус
        recency_factor = self._compute_recency_factor(source_trust.last_updated)

        # Итоговый score = база * (0.7 + 0.2 * count_factor + 0.1 * recency_factor)
        final = base * (0.7 + 0.2 * count_factor + 0.1 * recency_factor)
        return max(0.0, min(1.0, final))

    def _compute_recency_factor(self, last_updated: datetime) -> float:
        """Вычисляет фактор свежести данных."""
        delta = datetime.utcnow() - last_updated
        hours = delta.total_seconds() / 3600
        # Если обновление было менее часа назад – полный бонус, далее убывает
        if hours <= 1:
            return 1.0
        elif hours <= 24:
            return 0.5
        elif hours <= 168:  # неделя
            return 0.2
        else:
            return 0.0