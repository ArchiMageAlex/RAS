import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from common.models import Task, Event
from workspace_service.redis_client import WorkspaceService
from retriever_agent.agent import RetrieverAgent
from .checkpoint_manager import CheckpointManager
from .serialization import Checkpointable

logger = logging.getLogger(__name__)


class TaskOrchestrator:
    """Оркестратор задач: создаёт задачи и назначает агентов с поддержкой чекпоинтов."""

    def __init__(self, workspace: Optional[WorkspaceService] = None):
        self.workspace = workspace or WorkspaceService()
        self.retriever_agent = RetrieverAgent()
        self.checkpoint_manager = CheckpointManager(workspace=self.workspace)

    def create_task(self, event: Event, task_type: str = "retrieval") -> Task:
        """Создаёт задачу на основе события."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = Task(
            task_id=task_id,
            event_id=event.event_id,
            agent_type=task_type,
            status="created",
            parameters={
                "event_type": event.type.value,
                "severity": event.severity.value,
                "source": event.source,
            },
        )
        # Сохраняем в workspace
        self.workspace.add_active_task(task_id, task.dict())
        logger.info(f"Task created: {task_id} for event {event.event_id}")
        return task

    def assign_agent(self, task: Task) -> bool:
        """Назначает задачу агенту и запускает выполнение."""
        if task.agent_type == "retrieval":
            result = self.retriever_agent.execute(task)
            task.status = "completed" if result.get("success") else "failed"
            task.result = result
            task.updated_at = datetime.utcnow()
        else:
            logger.error(f"Unknown agent type: {task.agent_type}")
            task.status = "failed"
            task.result = {"error": "unknown_agent_type"}

        # Обновляем задачу в workspace
        self.workspace.add_active_task(task.task_id, task.dict())
        if task.status in ["completed", "failed"]:
            self.workspace.remove_active_task(task.task_id)
            logger.info(f"Task {task.task_id} finished with status {task.status}")
        return task.status == "completed"

    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Возвращает список активных задач."""
        tasks = self.workspace.get_active_tasks()
        return list(tasks.values())

    def cancel_task(self, task_id: str) -> bool:
        """Отменяет задачу."""
        tasks = self.workspace.get_active_tasks()
        if task_id in tasks:
            self.workspace.remove_active_task(task_id)
            logger.info(f"Task {task_id} cancelled.")
            return True
        return False


# Глобальный экземпляр
task_orchestrator = TaskOrchestrator()


def get_task_orchestrator() -> TaskOrchestrator:
    return task_orchestrator