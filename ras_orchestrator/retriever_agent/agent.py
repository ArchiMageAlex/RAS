import logging
import time
from typing import Dict, Any, List
from common.models import Task
from task_orchestrator.serialization import Checkpointable

logger = logging.getLogger(__name__)


class RetrieverAgent(Checkpointable):
    """Агент для поиска и обогащения информации с поддержкой чекпоинтов."""

    def __init__(self):
        # В реальности здесь была бы инициализация моделей, векторной БД и т.д.
        self.knowledge_base = [
            {"id": "kb1", "content": "Payment outage usually requires rollback to last stable version."},
            {"id": "kb2", "content": "Security alert may indicate compromised credentials."},
            {"id": "kb3", "content": "Performance degradation often linked to high database load."},
        ]
        # Состояние выполнения (можно хранить прогресс, кэш и т.д.)
        self.execution_state = {
            "processed_queries": [],
            "last_query": None,
            "results_cache": {},
            "start_time": time.time(),
        }

    def execute(self, task: Task) -> Dict[str, Any]:
        """Выполняет задачу retrieval."""
        logger.info(f"RetrieverAgent executing task {task.task_id}")
        # Имитация работы
        time.sleep(0.5)

        # Поиск релевантной информации в knowledge base
        query = f"{task.parameters.get('event_type', '')} {task.parameters.get('severity', '')}"
        self.execution_state["last_query"] = query
        self.execution_state["processed_queries"].append(query)

        results = self._search_knowledge(query)

        # Формирование ответа
        success = len(results) > 0
        return {
            "success": success,
            "task_id": task.task_id,
            "results": results,
            "summary": f"Found {len(results)} relevant documents.",
            "timestamp": time.time(),
        }

    def _search_knowledge(self, query: str) -> list:
        """Простой поиск по ключевым словам."""
        query_lower = query.lower()
        matches = []
        for item in self.knowledge_base:
            if any(word in item["content"].lower() for word in query_lower.split()):
                matches.append(item)
        return matches

    # Checkpointable interface
    def get_state(self) -> Dict[str, Any]:
        """
        Возвращает состояние агента для чекпоинта.
        """
        return {
            "knowledge_base": self.knowledge_base,
            "execution_state": self.execution_state,
            "timestamp": time.time(),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        """
        Восстанавливает состояние агента из чекпоинта.
        """
        self.knowledge_base = state.get("knowledge_base", self.knowledge_base)
        self.execution_state = state.get("execution_state", self.execution_state)
        logger.info("RetrieverAgent state restored from checkpoint")


# Глобальный экземпляр
retriever_agent = RetrieverAgent()


def get_retriever_agent() -> RetrieverAgent:
    return retriever_agent