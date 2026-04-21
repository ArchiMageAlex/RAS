"""
Historical Repository – абстракция для доступа к историческим событиям.
Поддерживает PostgreSQL и Redis кэш.
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from common.models import EventType, HistoricalEvent

logger = logging.getLogger(__name__)


class HistoricalRepository:
    """Репозиторий для работы с историческими событиями."""

    def __init__(self, postgres_connection=None, redis_client=None):
        """
        Инициализация репозитория.

        Параметры:
            postgres_connection: соединение с PostgreSQL (объект psycopg2)
            redis_client: клиент Redis для кэширования
        """
        self.postgres = postgres_connection
        self.redis = redis_client

    def get_events_in_window(
        self,
        event_type: Optional[EventType] = None,
        source: Optional[str] = None,
        window: timedelta = timedelta(days=7),
        limit: int = 1000
    ) -> List[HistoricalEvent]:
        """
        Возвращает исторические события за указанный период.

        Параметры:
            event_type: фильтр по типу события (опционально)
            source: фильтр по источнику (опционально)
            window: временное окно от текущего момента назад
            limit: максимальное количество событий
        """
        # Сначала проверяем кэш Redis, если доступен
        cache_key = self._build_cache_key(event_type, source, window)
        if self.redis:
            try:
                cached = self.redis.get(cache_key)
                if cached:
                    # В реальности нужно десериализовать список HistoricalEvent
                    logger.debug(f"Cache hit for key {cache_key}")
                    # Заглушка: возвращаем пустой список, т.к. кэширование требует сериализации
                    pass
            except Exception as e:
                logger.warning(f"Redis cache error: {e}")

        # Запрос к PostgreSQL
        events = self._query_postgres(event_type, source, window, limit)

        # Кэшируем результат
        if self.redis and events:
            try:
                # В реальности нужно сериализовать события
                # self.redis.setex(cache_key, timedelta(minutes=5), serialized)
                pass
            except Exception as e:
                logger.warning(f"Failed to cache events: {e}")

        return events

    def _query_postgres(
        self,
        event_type: Optional[EventType],
        source: Optional[str],
        window: timedelta,
        limit: int
    ) -> List[HistoricalEvent]:
        """Выполняет запрос к PostgreSQL."""
        if not self.postgres:
            logger.warning("PostgreSQL connection not available, returning empty list")
            return []

        try:
            cursor = self.postgres.cursor()
            query = """
                SELECT event_id, type, severity, source, timestamp, payload, novelty_score
                FROM historical_events
                WHERE timestamp >= %s
            """
            params = [datetime.utcnow() - window]

            if event_type:
                query += " AND type = %s"
                params.append(event_type.value)
            if source:
                query += " AND source = %s"
                params.append(source)

            query += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()

            events = []
            for row in rows:
                event = HistoricalEvent(
                    event_id=row[0],
                    type=EventType(row[1]),
                    severity=row[2],  # предполагается, что severity хранится как строка
                    source=row[3],
                    timestamp=row[4],
                    payload=row[5] if row[5] else {},
                    novelty_score=row[6]
                )
                events.append(event)
            return events
        except Exception as e:
            logger.error(f"PostgreSQL query failed: {e}")
            return []

    def save_event(self, event: HistoricalEvent) -> bool:
        """Сохраняет историческое событие в PostgreSQL."""
        if not self.postgres:
            logger.warning("PostgreSQL connection not available, cannot save event")
            return False

        try:
            cursor = self.postgres.cursor()
            query = """
                INSERT INTO historical_events
                (event_id, type, severity, source, timestamp, payload, novelty_score)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET
                    type = EXCLUDED.type,
                    severity = EXCLUDED.severity,
                    source = EXCLUDED.source,
                    timestamp = EXCLUDED.timestamp,
                    payload = EXCLUDED.payload,
                    novelty_score = EXCLUDED.novelty_score
            """
            cursor.execute(query, (
                event.event_id,
                event.type.value,
                event.severity.value if hasattr(event.severity, 'value') else event.severity,
                event.source,
                event.timestamp,
                event.payload,
                event.novelty_score
            ))
            self.postgres.commit()
            cursor.close()
            logger.debug(f"Saved historical event {event.event_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save historical event: {e}")
            return False

    def _build_cache_key(
        self,
        event_type: Optional[EventType],
        source: Optional[str],
        window: timedelta
    ) -> str:
        """Строит ключ для кэша Redis."""
        parts = ["historical"]
        if event_type:
            parts.append(event_type.value)
        if source:
            parts.append(source)
        parts.append(str(window.total_seconds()))
        return ":".join(parts)