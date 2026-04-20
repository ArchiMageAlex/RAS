import logging
from typing import Optional, Dict, Any
from datetime import datetime
from common.models import Event, SalienceScore, SystemMode
from policy_engine.engine import PolicyEngine

logger = logging.getLogger(__name__)


class InterruptDecision:
    def __init__(self, should_interrupt: bool, reason: str, priority: int = 0):
        self.should_interrupt = should_interrupt
        self.reason = reason
        self.priority = priority
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "should_interrupt": self.should_interrupt,
            "reason": self.reason,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat(),
        }


class InterruptManager:
    """Менеджер прерываний: решает, нужно ли прервать текущие задачи."""

    def __init__(self, policy_engine: Optional[PolicyEngine] = None):
        self.policy_engine = policy_engine or PolicyEngine()
        self.interrupt_history = []

    def evaluate(
        self,
        event: Event,
        salience_score: SalienceScore,
        current_mode: SystemMode,
        active_tasks: list,
    ) -> InterruptDecision:
        """Оценивает необходимость прерывания."""
        # 1. Проверка политик
        policy_result = self.policy_engine.evaluate_interrupt_policy(
            event, salience_score, current_mode, active_tasks
        )
        if policy_result.get("should_interrupt"):
            reason = policy_result.get("reason", "policy_triggered")
            decision = InterruptDecision(True, reason, priority=policy_result.get("priority", 1))
            self._record_decision(decision)
            return decision

        # 2. Эвристики на основе salience и режима
        if salience_score.aggregated > 0.8:
            reason = "high_salience"
            decision = InterruptDecision(True, reason, priority=2)
        elif current_mode == SystemMode.CRITICAL and salience_score.risk > 0.7:
            reason = "critical_mode_high_risk"
            decision = InterruptDecision(True, reason, priority=3)
        elif len(active_tasks) == 0:
            # Нет активных задач — прерывание не требуется
            decision = InterruptDecision(False, "no_active_tasks")
        else:
            decision = InterruptDecision(False, "no_interrupt_condition")

        self._record_decision(decision)
        return decision

    def _record_decision(self, decision: InterruptDecision):
        self.interrupt_history.append(decision)
        # Ограничиваем размер истории
        if len(self.interrupt_history) > 1000:
            self.interrupt_history.pop(0)
        logger.info(
            f"Interrupt decision: {decision.should_interrupt} "
            f"(reason: {decision.reason}, priority: {decision.priority})"
        )

    def get_recent_decisions(self, limit: int = 10):
        return [d.to_dict() for d in self.interrupt_history[-limit:]]


# Глобальный экземпляр
interrupt_manager = InterruptManager()


def get_interrupt_manager() -> InterruptManager:
    return interrupt_manager