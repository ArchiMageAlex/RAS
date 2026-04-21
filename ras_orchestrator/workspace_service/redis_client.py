import json
import logging
import os
from typing import Optional, Any, Dict, List
import redis

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Сервис рабочего пространства на основе Redis."""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        db: int = None,
    ):
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.db = db or int(os.getenv("REDIS_DB", "0"))
        logger.info(f"Connecting to Redis at {self.host}:{self.port}/{self.db}")
        self.redis_client = redis.Redis(
            host=self.host, port=self.port, db=self.db, decode_responses=True
        )
        self.prefix = "ras:workspace:"

    def _key(self, category: str, identifier: str) -> str:
        return f"{self.prefix}{category}:{identifier}"

    def store_event(self, event: Dict[str, Any], ttl: Optional[int] = None):
        """Сохраняет событие в workspace."""
        key = self._key("event", event.get("event_id", "unknown"))
        self.redis_client.set(key, json.dumps(event, default=str))
        if ttl:
            self.redis_client.expire(key, ttl)
        logger.debug(f"Event stored: {key}")

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Получает событие по ID."""
        key = self._key("event", event_id)
        data = self.redis_client.get(key)
        if data:
            return json.loads(data)
        return None

    def store_salience_score(self, event_id: str, score: Dict[str, Any]):
        """Сохраняет salience score."""
        key = self._key("salience", event_id)
        self.redis_client.set(key, json.dumps(score, default=str))
        logger.debug(f"Salience score stored for {event_id}")

    def get_salience_score(self, event_id: str) -> Optional[Dict[str, Any]]:
        key = self._key("salience", event_id)
        data = self.redis_client.get(key)
        if data:
            return json.loads(data)
        return None

    def set_mode(self, mode: str):
        """Устанавливает текущий режим системы."""
        self.redis_client.set(self._key("system", "mode"), mode)

    def get_mode(self) -> str:
        """Возвращает текущий режим системы."""
        return self.redis_client.get(self._key("system", "mode")) or "normal"

    def add_active_task(self, task_id: str, task_data: Dict[str, Any]):
        """Добавляет задачу в список активных."""
        key = self._key("tasks", "active")
        self.redis_client.hset(key, task_id, json.dumps(task_data, default=str))

    def remove_active_task(self, task_id: str):
        """Удаляет задачу из активных."""
        key = self._key("tasks", "active")
        self.redis_client.hdel(key, task_id)

    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Возвращает все активные задачи."""
        key = self._key("tasks", "active")
        tasks = self.redis_client.hgetall(key)
        result = {}
        for task_id, data in tasks.items():
            result[task_id] = json.loads(data)
        return result

    # Phase 2: Checkpoint storage
    def store_checkpoint(self, checkpoint_id: str, data: bytes, ttl: Optional[int] = None) -> bool:
        """Сохраняет чекпоинт в Redis."""
        key = self._key("checkpoint", checkpoint_id)
        try:
            # Используем set с binary данными
            self.redis_client.set(key, data)
            if ttl:
                self.redis_client.expire(key, ttl)
            logger.debug(f"Checkpoint stored: {checkpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to store checkpoint {checkpoint_id}: {e}")
            return False

    def get_checkpoint(self, checkpoint_id: str) -> Optional[bytes]:
        """Получает чекпоинт по ID."""
        key = self._key("checkpoint", checkpoint_id)
        try:
            data = self.redis_client.get(key)
            if data is None:
                return None
            # Redis возвращает bytes, если decode_responses=False, но у нас decode_responses=True
            # Чтобы избежать проблем, временно создадим отдельное соединение для бинарных данных
            # Упрощённо: предполагаем, что данные уже bytes
            if isinstance(data, str):
                return data.encode('utf-8')
            return data
        except Exception as e:
            logger.error(f"Failed to retrieve checkpoint {checkpoint_id}: {e}")
            return None

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Удаляет чекпоинт."""
        key = self._key("checkpoint", checkpoint_id)
        try:
            self.redis_client.delete(key)
            logger.debug(f"Checkpoint deleted: {checkpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
            return False

    def list_checkpoints(self, pattern: str = "*") -> List[str]:
        """Возвращает список ID чекпоинтов."""
        key_pattern = self._key("checkpoint", pattern)
        try:
            keys = self.redis_client.keys(key_pattern)
            # Убираем префикс
            prefix_len = len(self._key("checkpoint", ""))
            return [key[prefix_len:] for key in keys]
        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")
            return []

    def publish_update(self, channel: str, message: Dict[str, Any]):
        """Публикует обновление в Redis Pub/Sub."""
        self.redis_client.publish(channel, json.dumps(message, default=str))

    def health(self) -> bool:
        """Проверяет соединение с Redis."""
        try:
            return self.redis_client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Глобальный экземпляр
workspace_service = WorkspaceService()


def get_workspace_service() -> WorkspaceService:
    return workspace_service