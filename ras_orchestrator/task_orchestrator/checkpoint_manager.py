"""
Checkpoint Manager – управление чекпоинтами задач.
"""

import logging
import uuid
from typing import Optional, Tuple, Any
from datetime import datetime, timedelta
from common.models import Task, TaskCheckpoint
from workspace_service.redis_client import WorkspaceService
from .serialization import StateSerializer, Checkpointable, SerializationError

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Менеджер чекпоинтов для сохранения и восстановления состояния задач."""

    def __init__(self, workspace: Optional[WorkspaceService] = None):
        self.workspace = workspace or WorkspaceService()
        self.serializer = StateSerializer()

    def save_checkpoint(
        self,
        task: Task,
        agent_state: Any,
        ttl_seconds: int = 3600,
        format: str = "pickle"
    ) -> Optional[str]:
        """
        Сохраняет чекпоинт состояния агента для задачи.

        Параметры:
            task: объект задачи
            agent_state: состояние агента (должно быть сериализуемым)
            ttl_seconds: время жизни чекпоинта в секундах
            format: формат сериализации ('pickle' или 'json')

        Возвращает:
            ID чекпоинта или None в случае ошибки
        """
        if format not in ("pickle", "json"):
            raise ValueError(f"Unsupported serialization format: {format}")

        checkpoint_id = f"cp_{uuid.uuid4().hex[:8]}"

        try:
            # Сериализуем состояние
            state_data = self.serializer.serialize(agent_state, format=format)

            # Создаём объект чекпоинта
            checkpoint = TaskCheckpoint(
                checkpoint_id=checkpoint_id,
                task_id=task.task_id,
                agent_type=task.agent_type,
                state_data=state_data,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds) if ttl_seconds > 0 else None
            )

            # Сохраняем в workspace
            success = self.workspace.store_checkpoint(
                checkpoint_id,
                state_data,
                ttl=ttl_seconds if ttl_seconds > 0 else None
            )
            if not success:
                logger.error(f"Failed to store checkpoint {checkpoint_id} in workspace")
                return None

            logger.info(f"Checkpoint saved: {checkpoint_id} for task {task.task_id}")
            return checkpoint_id

        except SerializationError as e:
            logger.error(f"Serialization failed for task {task.task_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error saving checkpoint for task {task.task_id}: {e}")
            return None

    def load_checkpoint(self, checkpoint_id: str, format: str = "pickle") -> Optional[Tuple[Task, Any]]:
        """
        Загружает чекпоинт и возвращает задачу и состояние агента.

        Параметры:
            checkpoint_id: идентификатор чекпоинта
            format: формат сериализации

        Возвращает:
            Кортеж (Task, состояние агента) или None, если чекпоинт не найден
        """
        try:
            # Получаем данные из workspace
            data = self.workspace.get_checkpoint(checkpoint_id)
            if data is None:
                logger.warning(f"Checkpoint {checkpoint_id} not found")
                return None

            # Десериализуем состояние
            agent_state = self.serializer.deserialize(data, format=format)

            # Восстанавливаем задачу (пока что заглушка, т.к. Task не хранится в чекпоинте)
            # В реальности нужно хранить метаданные задачи отдельно
            # Для простоты создаём временную задачу
            task = Task(
                task_id="unknown",
                event_id="unknown",
                agent_type="unknown",
                status="checkpointed"
            )
            logger.info(f"Checkpoint loaded: {checkpoint_id}")
            return task, agent_state

        except SerializationError as e:
            logger.error(f"Deserialization failed for checkpoint {checkpoint_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading checkpoint {checkpoint_id}: {e}")
            return None

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Удаляет чекпоинт."""
        return self.workspace.delete_checkpoint(checkpoint_id)

    def list_checkpoints(self, pattern: str = "*") -> list:
        """Возвращает список ID чекпоинтов."""
        return self.workspace.list_checkpoints(pattern)

    def save_checkpoint_from_agent(
        self,
        task: Task,
        agent: Checkpointable,
        ttl_seconds: int = 3600,
        format: str = "pickle"
    ) -> Optional[str]:
        """
        Сохраняет чекпоинт, получая состояние от агента, реализующего Checkpointable.

        Параметры:
            task: задача
            agent: агент с методами get_state()
            ttl_seconds: время жизни
            format: формат сериализации

        Возвращает:
            ID чекпоинта или None
        """
        try:
            state = agent.get_state()
            return self.save_checkpoint(task, state, ttl_seconds, format)
        except NotImplementedError as e:
            logger.error(f"Agent does not implement get_state: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get state from agent: {e}")
            return None

    def restore_agent_from_checkpoint(
        self,
        checkpoint_id: str,
        agent: Checkpointable,
        format: str = "pickle"
    ) -> Optional[Task]:
        """
        Восстанавливает состояние агента из чекпоинта.

        Параметры:
            checkpoint_id: ID чекпоинта
            agent: агент, реализующий set_state()
            format: формат сериализации

        Возвращает:
            Задача, связанная с чекпоинтом, или None
        """
        result = self.load_checkpoint(checkpoint_id, format)
        if result is None:
            return None
        task, state = result
        try:
            agent.set_state(state)
            logger.info(f"Agent state restored from checkpoint {checkpoint_id}")
            return task
        except NotImplementedError as e:
            logger.error(f"Agent does not implement set_state: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to set state on agent: {e}")
            return None