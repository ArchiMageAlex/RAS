import logging
import time
from typing import Dict, Any
from common.models import Task

logger = logging.getLogger(__name__)


class RetrieverAgent:
    """Агент для поиска и обогащения информации."""

    def __init__(self):
        # В реальности здесь была бы инициализация моделей, векторной БД и т.д.
        self.knowledge_base = [
            {"id": "kb1", "content": "Payment outage usually requires rollback to last stable version."},
            {"id": "kb2", "content": "Security alert may indicate compromised credentials."},
            {"id": "kb3", "content": "Performance degradation often linked to high database load."},
        ]

    def execute(self, task: Task) -> Dict[str, Any]:
        """Выполняет задачу retrieval."""
        logger.info(f"RetrieverAgent executing task {task.task_id}")
        # Имитация работы
        time.sleep(0.5)

        # Поиск релевантной информации в knowledge base
        query = f"{task.parameters.get('event_type', '')} {task.parameters.get('severity', '')}"
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


# Глобальный экземпляр
retriever_agent = RetrieverAgent()


def get_retriever_agent() -> RetrieverAgent:
    return retriever_agent