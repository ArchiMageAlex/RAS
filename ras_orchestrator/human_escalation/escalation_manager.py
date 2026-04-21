"""
Escalation Manager – управление эскалациями, интеграция с Policy Engine и Task Orchestrator.
"""

import logging
from typing import Optional, Dict, Any
from common.models import Event
from workspace_service.redis_client import WorkspaceService
from policy_engine.engine import PolicyEngine
from .workflow_engine import WorkflowEngine
from .notifier import Notifier
from .models import EscalationWorkflow, EscalationInstance

logger = logging.getLogger(__name__)


class EscalationManager:
    """Менеджер эскалаций, координирующий workflows и уведомления."""

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        workspace: Optional[WorkspaceService] = None,
        workflow_engine: Optional[WorkflowEngine] = None,
        notifier: Optional[Notifier] = None,
    ):
        self.policy_engine = policy_engine or PolicyEngine()
        self.workspace = workspace or WorkspaceService()
        self.workflow_engine = workflow_engine or WorkflowEngine(workspace=self.workspace)
        self.notifier = notifier or Notifier()

    def evaluate_and_escalate(
        self,
        event: Event,
        salience_score: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[EscalationInstance]:
        """
        Оценивает необходимость эскалации и запускает workflow при необходимости.

        Параметры:
            event: событие
            salience_score: оценка значимости (словарь с полями relevance, risk и т.д.)
            context: дополнительный контекст

        Возвращает:
            Экземпляр эскалации или None, если эскалация не требуется
        """
        # Проверяем политики эскалации
        escalation_policy = self.policy_engine.evaluate_escalation_policy(
            event, salience_score, context or {}
        )
        if not escalation_policy.get("should_escalate", False):
            logger.debug(f"No escalation required for event {event.event_id}")
            return None

        # Получаем workflow из политики или используем дефолтный
        workflow_id = escalation_policy.get("workflow_id", "default_human_escalation")
        workflow = self._load_workflow(workflow_id)
        if not workflow:
            logger.warning(f"Workflow {workflow_id} not found, using default")
            workflow = self._create_default_workflow(event, escalation_policy)

        # Запускаем workflow
        instance = self.workflow_engine.start_workflow(
            workflow,
            event,
            policy_context=escalation_policy
        )
        logger.info(f"Escalation started: {instance.instance_id} for event {event.event_id}")
        return instance

    def _load_workflow(self, workflow_id: str) -> Optional[EscalationWorkflow]:
        """Загружает workflow по ID (заглушка)."""
        # В реальности workflow могут храниться в базе данных или YAML файлах
        # Пока возвращаем дефолтный workflow для примера
        if workflow_id == "default_human_escalation":
            return self._create_default_workflow(None, {})
        return None

    def _create_default_workflow(
        self,
        event: Optional[Event],
        policy: Dict[str, Any]
    ) -> EscalationWorkflow:
        """Создаёт дефолтный workflow эскалации."""
        from .models import EscalationStep, EscalationAction
        steps = [
            EscalationStep(
                action=EscalationAction.NOTIFY,
                parameters={
                    "channels": policy.get("notify_channels", ["slack", "email"]),
                    "message": f"Human escalation required for event {event.event_id if event else 'unknown'}",
                }
            ),
            EscalationStep(
                action=EscalationAction.WAIT_FOR_RESPONSE,
                parameters={
                    "timeout_seconds": policy.get("response_timeout", 300),
                    "instructions": "Please review and approve or reject the escalation.",
                },
                timeout_seconds=policy.get("response_timeout", 300)
            ),
            EscalationStep(
                action=EscalationAction.LOG,
                parameters={
                    "message": "Human response received, proceeding with next steps.",
                }
            ),
        ]
        return EscalationWorkflow(
            workflow_id="default_human_escalation",
            trigger_policy=policy.get("trigger", "high_risk"),
            steps=steps,
            timeout_seconds=3600,
            notify_channels=policy.get("notify_channels", ["slack", "email"]),
        )

    def get_instance(self, instance_id: str) -> Optional[EscalationInstance]:
        """Возвращает экземпляр эскалации по ID."""
        return self.workflow_engine._load_instance(instance_id)

    def list_active_instances(self) -> list:
        """Возвращает список активных экземпляров эскалации."""
        # В реальности нужно сканировать Redis ключи
        # Пока возвращаем пустой список
        return []

    def handle_human_response(
        self,
        instance_id: str,
        operator: str,
        decision: str,
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[EscalationInstance]:
        """
        Обрабатывает ответ оператора.

        Параметры:
            instance_id: ID экземпляра
            operator: идентификатор оператора
            decision: решение (approve, reject, escalate, etc.)
            notes: комментарии
            metadata: дополнительные данные

        Возвращает:
            Обновлённый экземпляр или None
        """
        from .models import HumanResponse
        response = HumanResponse(
            response_id=f"resp_{instance_id}",
            instance_id=instance_id,
            operator=operator,
            decision=decision,
            notes=notes,
            metadata=metadata or {}
        )
        return self.workflow_engine.handle_human_response(instance_id, response)