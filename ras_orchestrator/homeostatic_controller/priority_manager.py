"""
Менеджер приоритетов для динамической приоритизации задач и прерываний.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, UTC
from enum import Enum

logger = logging.getLogger(__name__)


class PriorityLevel(Enum):
    """Уровни приоритета."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class PriorityManager:
    """Управляет приоритетами задач и прерываний на основе текущей нагрузки."""

    def __init__(self):
        self.base_priorities: Dict[str, PriorityLevel] = {
            "payment_outage": PriorityLevel.CRITICAL,
            "security_alert": PriorityLevel.CRITICAL,
            "performance_degradation": PriorityLevel.HIGH,
            "user_complaint": PriorityLevel.NORMAL,
            "system_health": PriorityLevel.LOW,
            "custom": PriorityLevel.NORMAL,
        }
        self.current_adjustments: Dict[str, float] = {}  # event_type -> multiplier
        self.adjustment_history: List[Dict[str, Any]] = []
        self.last_recalculation = datetime.utcnow()

    async def initialize(self):
        """Инициализация менеджера."""
        logger.info("PriorityManager initialized.")

    async def shutdown(self):
        """Корректное завершение работы."""
        logger.info("PriorityManager shut down.")

    async def get_priority(self, event_type: str, system_load: float = 0.0) -> PriorityLevel:
        """
        Возвращает приоритет для типа события с учётом текущей нагрузки.
        system_load: 0.0 - 1.0, где 1.0 - максимальная нагрузка.
        """
        base = self.base_priorities.get(event_type, PriorityLevel.NORMAL)
        adjustment = self.current_adjustments.get(event_type, 1.0)

        # Корректировка на основе нагрузки: при высокой нагрузке повышаем приоритет критических событий
        if system_load > 0.8:
            if base == PriorityLevel.CRITICAL:
                adjustment *= 1.5
            elif base == PriorityLevel.HIGH:
                adjustment *= 1.2
            else:
                adjustment *= 0.8  # понижаем приоритет неважных событий

        # Применяем adjustment
        adjusted_value = base.value * adjustment
        # Ограничиваем диапазон
        adjusted_value = max(1, min(4, adjusted_value))

        # Округляем до ближайшего уровня
        for level in PriorityLevel:
            if abs(adjusted_value - level.value) <= 0.5:
                return level
        return PriorityLevel.NORMAL

    async def adjust_priorities(self, parameters: Dict[str, Any]) -> bool:
        """
        Корректирует приоритеты на основе параметров.
        Параметры могут включать:
          - event_type: тип события
          - multiplier: множитель приоритета
          - absolute_level: абсолютный уровень (1-4)
        """
        event_type = parameters.get("event_type")
        multiplier = parameters.get("multiplier")
        absolute_level = parameters.get("absolute_level")

        if event_type and event_type not in self.base_priorities:
            logger.warning(f"Unknown event type: {event_type}")
            return False

        if absolute_level is not None:
            try:
                level = PriorityLevel(absolute_level)
                # Преобразуем в множитель относительно базового
                base = self.base_priorities.get(event_type, PriorityLevel.NORMAL)
                multiplier = level.value / base.value
            except ValueError:
                logger.warning(f"Invalid absolute level: {absolute_level}")
                return False

        if multiplier is not None:
            if event_type:
                self.current_adjustments[event_type] = multiplier
                logger.info(f"Adjusted priority for {event_type}: multiplier={multiplier}")
            else:
                # Применить ко всем типам
                for et in self.base_priorities:
                    self.current_adjustments[et] = multiplier
                logger.info(f"Adjusted all priorities: multiplier={multiplier}")

        # Запись в историю
        self.adjustment_history.append({
            "timestamp": datetime.now(UTC),
            "parameters": parameters,
            "adjustments": self.current_adjustments.copy(),
        })
        self.last_recalculation = datetime.now(UTC)
        return True

    async def recalculate_based_on_metrics(self, metrics: Dict[str, float]):
        """
        Пересчитывает приоритеты на основе системных метрик.
        Метрики могут включать: cpu_load, latency_ms, error_rate, queue_depth.
        """
        # Простая эвристика
        cpu_load = metrics.get("cpu_load", 0.0)
        latency = metrics.get("latency_ms", 0.0)
        error_rate = metrics.get("error_rate", 0.0)
        queue_depth = metrics.get("queue_depth", 0)

        # Вычисляем общий фактор нагрузки
        load_factor = cpu_load * 0.4 + min(latency / 500, 1.0) * 0.3 + error_rate * 10 * 0.2 + min(queue_depth / 100, 1.0) * 0.1

        # Корректируем приоритеты
        for event_type in self.base_priorities:
            base = self.base_priorities[event_type]
            if base == PriorityLevel.CRITICAL:
                multiplier = 1.0 + load_factor * 0.5  # повышаем до 1.5x
            elif base == PriorityLevel.HIGH:
                multiplier = 1.0 + load_factor * 0.3
            elif base == PriorityLevel.NORMAL:
                multiplier = 1.0 - load_factor * 0.2
            else:  # LOW
                multiplier = 1.0 - load_factor * 0.4

            self.current_adjustments[event_type] = max(0.5, min(2.0, multiplier))

        logger.debug(f"Recalculated priorities based on load factor {load_factor:.2f}")

    async def get_status(self) -> Dict[str, Any]:
        """Возвращает текущий статус менеджера приоритетов."""
        current = {}
        for event_type, base in self.base_priorities.items():
            adjustment = self.current_adjustments.get(event_type, 1.0)
            current[event_type] = {
                "base": base.name,
                "adjustment": adjustment,
                "effective": base.value * adjustment,
            }

        return {
            "current_priorities": current,
            "last_recalculation": self.last_recalculation.isoformat(),
            "adjustment_count": len(self.adjustment_history),
        }