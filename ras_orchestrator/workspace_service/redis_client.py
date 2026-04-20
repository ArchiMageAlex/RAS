import json
import logging
from typing import Optional, Any, Dict, List
import redis

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Сервис рабочего пространства на основе Redis."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
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