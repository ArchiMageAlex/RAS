"""
Source Registry – реестр источников с метриками доверия.
Хранит и обновляет SourceTrust объекты.
"""

import logging
from typing import Dict, Optional
from datetime import datetime
from common.models import SourceTrust

logger = logging.getLogger(__name__)


class SourceRegistry:
    """Реестр источников для trust scoring."""

    def __init__(self, storage_backend=None):
        """
        Инициализация реестра.

        Параметры:
            storage_backend: бэкенд хранения (например, Redis, PostgreSQL).
                             Если None, используется in-memory словарь.
        """
        self.storage = storage_backend
        self.in_memory: Dict[str, SourceTrust] = {}

    def get_or_create(self, source: str) -> SourceTrust:
        """Возвращает запись SourceTrust для источника, создавая при необходимости."""
        # Пытаемся получить из бэкенда
        if self.storage:
            try:
                stored = self._load_from_storage(source)
                if stored:
                    return stored
            except Exception as e:
                logger.warning(f"Failed to load source {source} from storage: {e}")

        # Проверяем in-memory кэш
        if source in self.in_memory:
            return self.in_memory[source]

        # Создаём новую запись
        new_trust = SourceTrust(
            source=source,
            trust_score=0.5,
            events_count=0,
            accuracy=1.0,
            last_updated=datetime.utcnow()
        )
        self.in_memory[source] = new_trust
        return new_trust

    def save(self, source_trust: SourceTrust) -> None:
        """Сохраняет или обновляет запись источника."""
        self.in_memory[source_trust.source] = source_trust

        if self.storage:
            try:
                self._save_to_storage(source_trust)
            except Exception as e:
                logger.error(f"Failed to save source {source_trust.source} to storage: {e}")

    def _load_from_storage(self, source: str) -> Optional[SourceTrust]:
        """Загружает SourceTrust из внешнего хранилища (заглушка)."""
        # В реальной реализации здесь будет запрос к PostgreSQL или Redis
        # Пока возвращаем None, чтобы использовать in-memory
        return None

    def _save_to_storage(self, source_trust: SourceTrust) -> None:
        """Сохраняет SourceTrust во внешнее хранилище (заглушка)."""
        # В реальной реализации здесь будет запись в PostgreSQL или Redis
        pass

    def get_trust_score(self, source: str) -> float:
        """Возвращает текущий trust score источника."""
        trust = self.get_or_create(source)
        return trust.trust_score

    def update_trust_score(self, source: str, new_score: float) -> None:
        """Обновляет trust score источника."""
        trust = self.get_or_create(source)
        trust.trust_score = max(0.0, min(1.0, new_score))
        trust.last_updated = datetime.utcnow()
        self.save(trust)