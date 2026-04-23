"""
Checkpoint Integration – интеграция Interrupt Manager с Checkpoint Manager.
"""

import logging
from typing import List
from common.models import Task
from task_orchestrator.checkpoint_manager import CheckpointManager
from task_orchestrator.serialization import Checkpointable

logger = logging.getLogger(__name__)


class CheckpointIntegration:
    """Мост между Interrupt Manager и Checkpoint Manager."""

    def __init__(self, checkpoint_manager: CheckpointManager):
        self.checkpoint_manager = checkpoint_manager

    def create_checkpoints_for_tasks(
        self,
        tasks: List[Task],
        agents: List[Checkpointable],
        ttl_seconds: int = 3600
    ) -> List[str]:
        """
        Создаёт чекпоинты для списка задач и соответствующих агентов.

        Параметры:
            tasks: список задач
            agents: список агентов (должны соответствовать задачам по порядку)
            ttl_seconds: время жизни чекпоинта

        Возвращает:
            Список ID созданных чекпоинтов
        """
        checkpoint_ids = []
        for task, agent in zip(tasks, agents):
            if not isinstance(agent, Checkpointable):
                logger.warning(f"Agent for task {task.task_id} is not Checkpointable, skipping")
                continue
            cp_id = self.checkpoint_manager.save_checkpoint_from_agent(
                task, agent, ttl_seconds=ttl_seconds
            )
            if cp_id:
                checkpoint_ids.append(cp_id)
                logger.info(f"Checkpoint created for task {task.task_id}: {cp_id}")
            else:
                logger.error(f"Failed to create checkpoint for task {task.task_id}")
        return checkpoint_ids

    def restore_tasks_from_checkpoints(
        self,
        checkpoint_ids: List[str],
        agents: List[Checkpointable]
    ) -> List[Task]:
        """
        Восстанавливает задачи из чекпоинтов.

        Параметры:
            checkpoint_ids: список ID чекпоинтов
            agents: список агентов для восстановления состояния

        Возвращает:
            Список восстановленных задач
        """
        restored_tasks = []
        for cp_id, agent in zip(checkpoint_ids, agents):
            if not isinstance(agent, Checkpointable):
                logger.warning(f"Agent for checkpoint {cp_id} is not Checkpointable, skipping")
                continue
            task = self.checkpoint_manager.restore_agent_from_checkpoint(cp_id, agent)
            if task:
                restored_tasks.append(task)
                logger.info(f"Task restored from checkpoint {cp_id}")
            else:
                logger.error(f"Failed to restore from checkpoint {cp_id}")
        return restored_tasks