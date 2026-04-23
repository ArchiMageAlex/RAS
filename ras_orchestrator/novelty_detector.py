"""
Novelty Detection - заглушка для фазы 2.
Обнаружение новизны событий на основе исторических паттернов.
"""

import logging
from typing import Dict, Any, Optional
from common.models import Event

logger = logging.getLogger(__name__)


class NoveltyDetector:
    """Детектор новизны событий."""

    def __init__(self, historical_repository=None):
        self.historical_repository = historical_repository

    async def compute_novelty(self, event: Event) -> float:
        """
        Вычисляет показатель новизны события (0.0 - 1.0).
        1.0 - совершенно новое, 0.0 - часто встречающееся.
        """
        # Заглушка: возвращаем фиксированное значение
        # В реальной реализации сравниваем с историческими событиями
        return 0.3

    async def update_model(self, event: Event, human_feedback: Optional[float] = None):
        """Обновляет модель новизны на основе нового события и обратной связи."""
        logger.debug(f"Updating novelty model with event {event.event_id}")

    async def get_novelty_stats(self) -> Dict[str, Any]:
        """Возвращает статистику детектора."""
        return {"total_processed": 0, "avg_novelty": 0.5}


# Глобальный экземпляр
novelty_detector = NoveltyDetector()