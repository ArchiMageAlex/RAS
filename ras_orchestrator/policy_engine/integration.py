"""
Интеграция Policy Engine с компонентами оркестратора.
"""
import logging
from typing import Dict, Any, List, Optional
from .core import PolicyEngineCore, get_global_engine
from common.models import Event, SalienceScore, SystemMode, Task

logger = logging.getLogger(__name__)


class PolicyIntegration:
    """Базовый класс интеграции политик с компонентами."""

    def __init__(self, engine: Optional[PolicyEngineCore] = None):
        self.engine = engine or get_global_engine(watch=False)

    def evaluate(self, policy_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Оценивает политики заданного типа."""
        return self.engine.evaluate(policy_type, context)


class SalienceEnginePolicyIntegration(PolicyIntegration):
    """Интеграция с Salience Engine для корректировки весов и anomaly detection."""

    def adjust_weights(self, event: Event, current_weights: Dict[str, float]) -> Dict[str, float]:
        """Корректирует веса scoring на основе политик."""
        context = {
            "event": event.dict(),
            "current_weights": current_weights,
        }
        matched = self.evaluate("salience_weights", context)
        if matched:
            # Применяем действия первой совпавшей политики
            actions = matched[0].get("actions", {})
            adjustments = actions.get("weight_adjustments", {})
            for key, adj in adjustments.items():
                if key in current_weights:
                    current_weights[key] = max(0.0, min(1.0, current_weights[key] + adj))
            logger.info(f"Adjusted weights via policy: {current_weights}")
        return current_weights

    def detect_anomaly_policy(self, salience_score: SalienceScore) -> Dict[str, Any]:
        """Определяет, является ли salience score аномалией на основе политик."""
        context = {"salience": salience_score.dict()}
        matched = self.evaluate("salience_anomaly", context)
        if matched:
            return matched[0].get("actions", {})
        return {}


class ModeManagerPolicyIntegration(PolicyIntegration):
    """Интеграция с Mode Manager для переключения режимов с hysteresis."""

    def evaluate_mode_transition(
        self,
        salience_score: SalienceScore,
        current_mode: SystemMode,
        system_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Оценивает необходимость переключения режима с учётом политик."""
        context = {
            "salience": salience_score.dict(),
            "current_mode": current_mode.value,
            "system_metrics": system_metrics,
        }
        matched = self.evaluate("mode", context)
        if matched:
            return matched[0].get("actions", {})
        return {}

    def get_hysteresis(self, current_mode: SystemMode) -> Dict[str, float]:
        """Возвращает значения гистерезиса для режима из политик."""
        context = {"current_mode": current_mode.value}
        matched = self.evaluate("mode_hysteresis", context)
        if matched:
            return matched[0].get("actions", {})
        return {"up": 0.05, "down": 0.03}  # default


class InterruptManagerPolicyIntegration(PolicyIntegration):
    """Интеграция с Interrupt Manager для типов прерываний и checkpointing."""

    def evaluate_interrupt(
        self,
        event: Event,
        salience_score: SalienceScore,
        current_mode: SystemMode,
        active_tasks: List[Task],
    ) -> Dict[str, Any]:
        """Оценивает прерывание с использованием политик."""
        context = {
            "event": event.dict(),
            "salience": salience_score.dict(),
            "current_mode": current_mode.value,
            "active_task_count": len(active_tasks),
            "active_tasks": [t.dict() for t in active_tasks],
        }
        matched = self.evaluate("interrupt", context)
        if matched:
            return matched[0].get("actions", {})
        return {}

    def get_checkpoint_policy(self, task: Task) -> Dict[str, Any]:
        """Возвращает политику создания чекпоинта для задачи."""
        context = {"task": task.dict()}
        matched = self.evaluate("checkpoint", context)
        if matched:
            return matched[0].get("actions", {})
        return {"enabled": True, "ttl_seconds": 86400}


class TaskOrchestratorPolicyIntegration(PolicyIntegration):
    """Интеграция с Task Orchestrator для маршрутизации и приоритизации."""

    def route_task(self, task: Task, available_workers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Определяет маршрутизацию задачи на основе политик."""
        context = {
            "task": task.dict(),
            "available_workers": available_workers,
            "worker_count": len(available_workers),
        }
        matched = self.evaluate("routing", context)
        if matched:
            return matched[0].get("actions", {})
        return {"target_worker": None, "load_balancing": "round_robin"}

    def prioritize_tasks(self, tasks: List[Task]) -> List[Task]:
        """Приоритизирует список задач на основе политик."""
        context = {"tasks": [t.dict() for t in tasks]}
        matched = self.evaluate("task_priority", context)
        if matched:
            actions = matched[0].get("actions", {})
            priority_map = actions.get("priority_map", {})
            # Применяем приоритеты
            for task in tasks:
                if task.task_id in priority_map:
                    task.priority = priority_map[task.task_id]
        return sorted(tasks, key=lambda t: t.priority, reverse=True)


class AgentLayerPolicyIntegration(PolicyIntegration):
    """Интеграция с Agent Layer для контроля действий и tool access."""

    def check_action_permission(
        self, agent_id: str, action: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Проверяет разрешение на действие."""
        context.update({"agent_id": agent_id, "action": action})
        matched = self.evaluate("action", context)
        if matched:
            return matched[0].get("actions", {})
        return {"allowed": True, "reason": "no_policy"}

    def check_tool_access(
        self, agent_id: str, tool: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Проверяет доступ к инструменту."""
        context.update({"agent_id": agent_id, "tool": tool})
        matched = self.evaluate("tool_access", context)
        if matched:
            return matched[0].get("actions", {})
        return {"allowed": True, "usage_limit": None}


class HumanEscalationPolicyIntegration(PolicyIntegration):
    """Интеграция с Human Escalation для передачи человеку."""

    def evaluate_escalation(
        self,
        event: Event,
        salience_score: SalienceScore,
        decision_confidence: float,
    ) -> Dict[str, Any]:
        """Оценивает необходимость эскалации к человеку."""
        context = {
            "event": event.dict(),
            "salience": salience_score.dict(),
            "decision_confidence": decision_confidence,
        }
        matched = self.evaluate("human_escalation", context)
        if matched:
            return matched[0].get("actions", {})
        return {"escalate": False, "level": "low"}


# Глобальные экземпляры интеграций
salience_integration = SalienceEnginePolicyIntegration()
mode_integration = ModeManagerPolicyIntegration()
interrupt_integration = InterruptManagerPolicyIntegration()
task_integration = TaskOrchestratorPolicyIntegration()
agent_integration = AgentLayerPolicyIntegration()
human_integration = HumanEscalationPolicyIntegration()


def get_integration(component: str) -> PolicyIntegration:
    """Возвращает интеграцию для указанного компонента."""
    integrations = {
        "salience": salience_integration,
        "mode": mode_integration,
        "interrupt": interrupt_integration,
        "task": task_integration,
        "agent": agent_integration,
        "human": human_integration,
    }
    return integrations.get(component, PolicyIntegration())