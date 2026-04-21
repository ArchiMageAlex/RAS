"""
Workflow Engine – движок выполнения workflows эскалации.
"""

import logging
import uuid
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from common.models import Event
from workspace_service.redis_client import WorkspaceService
from .models import (
    EscalationWorkflow,
    EscalationInstance,
    EscalationStep,
    EscalationAction,
    HumanResponse,
)
from .notifier import Notifier

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Движок выполнения workflows эскалации."""

    def __init__(
        self,
        workspace: Optional[WorkspaceService] = None,
        notifier: Optional[Notifier] = None,
    ):
        self.workspace = workspace or WorkspaceService()
        self.notifier = notifier or Notifier()
        self.prefix = "ras:escalation:"

    def _key(self, category: str, identifier: str) -> str:
        return f"{self.prefix}{category}:{identifier}"

    def start_workflow(
        self,
        workflow: EscalationWorkflow,
        event: Event,
        policy_context: Dict[str, Any]
    ) -> EscalationInstance:
        """
        Запускает workflow эскалации для события.

        Параметры:
            workflow: workflow для выполнения
            event: событие, вызвавшее эскалацию
            policy_context: контекст из Policy Engine

        Возвращает:
            Экземпляр запущенного workflow
        """
        instance_id = f"escalation_{uuid.uuid4().hex[:8]}"
        timeout_at = None
        if workflow.timeout_seconds > 0:
            timeout_at = datetime.utcnow() + timedelta(seconds=workflow.timeout_seconds)

        instance = EscalationInstance(
            instance_id=instance_id,
            workflow_id=workflow.workflow_id,
            event_id=event.event_id,
            status="running",
            current_step=0,
            step_results=[],
            started_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            timeout_at=timeout_at,
        )

        # Сохраняем в workspace
        self._save_instance(instance)
        logger.info(f"Escalation workflow started: {instance_id} for event {event.event_id}")

        # Запускаем выполнение асинхронно (можно через фоновую задачу)
        # В реальности здесь можно использовать asyncio.create_task или очередь задач
        # Для простоты вызовем execute_step синхронно
        self._execute_step(instance, workflow)

        return instance

    def _execute_step(self, instance: EscalationInstance, workflow: EscalationWorkflow):
        """Выполняет текущий шаг workflow."""
        if instance.current_step >= len(workflow.steps):
            instance.status = "completed"
            instance.updated_at = datetime.utcnow()
            self._save_instance(instance)
            logger.info(f"Workflow {instance.instance_id} completed")
            return

        step = workflow.steps[instance.current_step]
        logger.info(
            f"Executing step {instance.current_step + 1}/{len(workflow.steps)} "
            f"for instance {instance.instance_id}: {step.action}"
        )

        try:
            result = self._perform_step_action(step, instance, workflow)
            instance.step_results.append({
                "step": instance.current_step,
                "action": step.action,
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            })
            instance.current_step += 1
            instance.updated_at = datetime.utcnow()

            # Если шаг был WAIT_FOR_RESPONSE, переводим в ожидание
            if step.action == EscalationAction.WAIT_FOR_RESPONSE:
                instance.status = "waiting_for_response"
                self._save_instance(instance)
                logger.info(f"Workflow {instance.instance_id} waiting for human response")
                return

            # Продолжаем выполнение следующего шага
            self._execute_step(instance, workflow)
        except Exception as e:
            logger.error(f"Step execution failed for instance {instance.instance_id}: {e}")
            instance.status = "failed"
            instance.updated_at = datetime.utcnow()
            self._save_instance(instance)

    def _perform_step_action(
        self,
        step: EscalationStep,
        instance: EscalationInstance,
        workflow: EscalationWorkflow
    ) -> Dict[str, Any]:
        """Выполняет конкретное действие шага."""
        if step.action == EscalationAction.NOTIFY:
            return self._action_notify(step, instance, workflow)
        elif step.action == EscalationAction.WAIT_FOR_RESPONSE:
            return self._action_wait_for_response(step, instance, workflow)
        elif step.action == EscalationAction.EXECUTE_SCRIPT:
            return self._action_execute_script(step, instance, workflow)
        elif step.action == EscalationAction.CREATE_TASK:
            return self._action_create_task(step, instance, workflow)
        elif step.action == EscalationAction.LOG:
            return self._action_log(step, instance, workflow)
        else:
            raise ValueError(f"Unknown action: {step.action}")

    def _action_notify(
        self,
        step: EscalationStep,
        instance: EscalationInstance,
        workflow: EscalationWorkflow
    ) -> Dict[str, Any]:
        """Отправляет уведомление через Notifier."""
        channels = step.parameters.get("channels", workflow.notify_channels)
        message = step.parameters.get("message", f"Escalation required for event {instance.event_id}")
        data = {
            "event_id": instance.event_id,
            "instance_id": instance.instance_id,
            "workflow_id": workflow.workflow_id,
            "message": message,
        }
        sent = self.notifier.send(channels, data)
        return {"channels": channels, "sent": sent}

    def _action_wait_for_response(
        self,
        step: EscalationStep,
        instance: EscalationInstance,
        workflow: EscalationWorkflow
    ) -> Dict[str, Any]:
        """Устанавливает ожидание ответа оператора."""
        timeout = step.timeout_seconds or 300
        return {"timeout_seconds": timeout, "status": "waiting"}

    def _action_execute_script(
        self,
        step: EscalationStep,
        instance: EscalationInstance,
        workflow: EscalationWorkflow
    ) -> Dict[str, Any]:
        """Выполняет скрипт (заглушка)."""
        script = step.parameters.get("script", "")
        logger.info(f"Executing script for instance {instance.instance_id}: {script[:50]}...")
        # В реальности здесь можно выполнить внешний скрипт или вызвать API
        return {"script_executed": True, "output": "stub"}

    def _action_create_task(
        self,
        step: EscalationStep,
        instance: EscalationInstance,
        workflow: EscalationWorkflow
    ) -> Dict[str, Any]:
        """Создаёт задачу в Task Orchestrator (заглушка)."""
        task_type = step.parameters.get("task_type", "human_review")
        logger.info(f"Creating task of type {task_type} for instance {instance.instance_id}")
        # Интеграция с Task Orchestrator будет позже
        return {"task_created": True, "task_type": task_type}

    def _action_log(
        self,
        step: EscalationStep,
        instance: EscalationInstance,
        workflow: EscalationWorkflow
    ) -> Dict[str, Any]:
        """Логирует информацию."""
        message = step.parameters.get("message", "")
        logger.info(f"Escalation log: {message}")
        return {"logged": True, "message": message}

    def handle_human_response(
        self,
        instance_id: str,
        response: HumanResponse
    ) -> Optional[EscalationInstance]:
        """
        Обрабатывает ответ оператора и продолжает workflow.

        Параметры:
            instance_id: ID экземпляра
            response: ответ оператора

        Возвращает:
            Обновлённый экземпляр или None, если не найден
        """
        instance = self._load_instance(instance_id)
        if not instance:
            logger.error(f"Instance {instance_id} not found")
            return None
        if instance.status != "waiting_for_response":
            logger.warning(f"Instance {instance_id} is not waiting for response")
            return instance

        instance.human_response = response.dict()
        instance.status = "running"
        instance.updated_at = datetime.utcnow()
        self._save_instance(instance)

        # Загружаем workflow и продолжаем выполнение
        workflow = self._load_workflow(instance.workflow_id)
        if workflow:
            self._execute_step(instance, workflow)
        else:
            logger.error(f"Workflow {instance.workflow_id} not found")
            instance.status = "failed"
            self._save_instance(instance)

        return instance

    def _save_instance(self, instance: EscalationInstance) -> None:
        """Сохраняет экземпляр в workspace."""
        key = self._key("instance", instance.instance_id)
        self.workspace.redis_client.set(
            key,
            instance.json(),
            ex=86400,  # TTL 24 часа
        )

    def _load_instance(self, instance_id: str) -> Optional[EscalationInstance]:
        """Загружает экземпляр из workspace."""
        key = self._key("instance", instance_id)
        data = self.workspace.redis_client.get(key)
        if data:
            return EscalationInstance.parse_raw(data)
        return None

    def _load_workflow(self, workflow_id: str) -> Optional[EscalationWorkflow]:
        """Загружает workflow по ID (заглушка)."""
        # В реальности workflow могут храниться в базе данных или конфигурационных файлах
        # Пока возвращаем None, чтобы не усложнять
        return None