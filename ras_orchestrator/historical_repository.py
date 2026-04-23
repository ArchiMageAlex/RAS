"""
Historical Events Store - заглушка для фазы 2.
Предоставляет интерфейс для доступа к историческим событиям.
В реальной реализации должен подключаться к БД (PostgreSQL/TimescaleDB).
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from common.models import Event

logger = logging.getLogger(__name__)


class HistoricalRepository:
    """Репозиторий исторических событий."""

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string
        self.events: List[Event] = []  # временное хранение в памяти

    async def store_event(self, event: Event) -> None:
        """Сохраняет событие в историю."""
        self.events.append(event)
        logger.debug(f"Event stored: {event.event_id}")

    async def get_events(
        self,
        start_time: datetime,
        end_time: datetime,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Event]:
        """Возвращает события за указанный период."""
        filtered = [
            e for e in self.events
            if start_time <= e.timestamp <= end_time
            and (event_type is None or e.event_type == event_type)
            and (source is None or e.source == source)
        ]
        return filtered[:limit]

    async def aggregate_salience_by_hour(
        self, start_time: datetime, end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Агрегирует значимость по часам (для временных рядов)."""
        # Заглушка: возвращает пустой список
        return []


# Глобальный экземпляр для использования в других модулях
historical_repository = HistoricalRepository()