import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from common.models import Event, SalienceScore, SystemMode, Task
from policy_engine.engine import PolicyEngine
from workspace_service.redis_client import WorkspaceService

logger = logging.getLogger(__name__)


class InterruptType(str, Enum):
    """Типы прерываний."""
    SOFT = "soft"      # Прерывание с возможностью graceful shutdown
    HARD = "hard"      # Немедленное прерывание
    DELAYED = "delayed"  # Прерывание с задержкой (например, через N секунд)


class InterruptDecision:
    """Расширенное решение о прерывании."""

    def __init__(
        self,
        should_interrupt: bool,
        reason: str,
        interrupt_type: InterruptType = InterruptType.SOFT,
        priority: int = 0,
        delay_seconds: int = 0,
        checkpoint_required: bool = False,
    ):
        self.should_interrupt = should_interrupt
        self.reason = reason
        self.interrupt_type = interrupt_type
        self.priority = priority
        self.delay_seconds = delay_seconds
        self.checkpoint_required = checkpoint_required
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "should_interrupt": self.should_interrupt,
            "reason": self.reason,
            "interrupt_type": self.interrupt_type.value,
            "priority": self.priority,
            "delay_seconds": self.delay_seconds,
            "checkpoint_required": self.checkpoint_required,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TaskCheckpoint:
    """Чекпоинт задачи для возможности возобновления."""
    task_id: str
    checkpoint_data: Dict[str, Any]
    created_at: datetime
    expires_at: Optional[datetime] = None


class InterruptManager:
    """
    Улучшенный менеджер прерываний с поддержкой типов прерываний,
    чекпоинтов, политик возобновления и интеграции с workspace service.
    """

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        workspace_service: Optional[WorkspaceService] = None,
    ):
        self.policy_engine = policy_engine or PolicyEngine()
        self.workspace_service = workspace_service or WorkspaceService()
        self.interrupt_history: List[InterruptDecision] = []
        self.checkpoints: Dict[str, TaskCheckpoint] = {}

    def evaluate(
        self,
        event: Event,
        salience_score: SalienceScore,
        current_mode: SystemMode,
        active_tasks: List[Task],
    ) -> InterruptDecision:
        """
        Оценивает необходимость прерывания с улучшенной логикой.
        """
        # 1. Проверка политик (приоритет)
        policy_result = self.policy_engine.evaluate_interrupt_policy(
            event, salience_score, current_mode, active_tasks
        )
        if policy_result.get("should_interrupt"):
            reason = policy_result.get("reason", "policy_triggered")
            interrupt_type = InterruptType(policy_result.get("interrupt_type", "soft"))
            decision = InterruptDecision(
                True,
                reason,
                interrupt_type=interrupt_type,
                priority=policy_result.get("priority", 1),
                delay_seconds=policy_result.get("delay_seconds", 0),
                checkpoint_required=policy_result.get("checkpoint_required", False),
            )
            self._record_decision(decision)
            if decision.checkpoint_required:
                self._create_checkpoints(active_tasks)
            return decision

        # 2. Эвристики на основе salience, режима и системных метрик
        decision = self._heuristic_evaluation(event, salience_score, current_mode, active_tasks)
        self._record_decision(decision)

        # 3. Если прерывание требуется, создаём чекпоинты для задач
        if decision.should_interrupt and decision.checkpoint_required:
            self._create_checkpoints(active_tasks)

        return decision

    def _heuristic_evaluation(
        self,
        event: Event,
        salience_score: SalienceScore,
        current_mode: SystemMode,
        active_tasks: List[Task],
    ) -> InterruptDecision:
        """Эвристическая оценка на основе множества факторов."""
        if len(active_tasks) == 0:
            return InterruptDecision(False, "no_active_tasks")

        aggregated = salience_score.aggregated
        risk = salience_score.risk
        urgency = salience_score.urgency

        # Матрица решений
        if aggregated > 0.9 and risk > 0.8:
            return InterruptDecision(
                True,
                "extreme_risk_and_salience",
                interrupt_type=InterruptType.HARD,
                priority=5,
                checkpoint_required=True,
            )
        elif current_mode == SystemMode.CRITICAL and aggregated > 0.7:
            return InterruptDecision(
                True,
                "critical_mode_high_salience",
                interrupt_type=InterruptType.HARD,
                priority=4,
                checkpoint_required=True,
            )
        elif aggregated > 0.8:
            return InterruptDecision(
                True,
                "high_salience",
                interrupt_type=InterruptType.SOFT,
                priority=3,
                checkpoint_required=True,
            )
        elif current_mode == SystemMode.ELEVATED and risk > 0.6:
            return InterruptDecision(
                True,
                "elevated_mode_risk",
                interrupt_type=InterruptType.DELAYED,
                delay_seconds=10,
                priority=2,
                checkpoint_required=False,
            )
        elif urgency > 0.8 and aggregated > 0.6:
            return InterruptDecision(
                True,
                "high_urgency",
                interrupt_type=InterruptType.SOFT,
                priority=2,
                checkpoint_required=False,
            )
        else:
            return InterruptDecision(False, "no_interrupt_condition")

    def _create_checkpoints(self, tasks: List[Task]):
        """Создаёт чекпоинты для задач и сохраняет в workspace."""
        for task in tasks:
            checkpoint = TaskCheckpoint(
                task_id=task.task_id,
                checkpoint_data={
                    "task": task.model_dump(),
                    "progress": task.parameters.get("progress", 0),
                    "state": "interrupted",
                },
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=24),
            )
            self.checkpoints[task.task_id] = checkpoint
            # Сохраняем в workspace service
            if self.workspace_service:
                key = f"checkpoint:{task.task_id}"
                self.workspace_service.redis_client.set(
                    key,
                    checkpoint.checkpoint_data,
                    ex=86400,  # TTL 24 часа
                )
            logger.info(f"Checkpoint created for task {task.task_id}")

    def restore_from_checkpoint(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Восстанавливает состояние задачи из чекпоинта."""
        if task_id in self.checkpoints:
            checkpoint = self.checkpoints[task_id]
            logger.info(f"Restoring task {task_id} from memory checkpoint")
            return checkpoint.checkpoint_data

        # Пробуем загрузить из workspace
        if self.workspace_service:
            key = f"checkpoint:{task_id}"
            data = self.workspace_service.redis_client.get(key)
            if data:
                logger.info(f"Restoring task {task_id} from workspace checkpoint")
                return data
        return None

    def get_resumption_policy(self, task_id: str) -> Dict[str, Any]:
        """
        Возвращает политику возобновления для прерванной задачи.
        Может зависеть от типа прерывания, приоритета и других факторов.
        """
        # Базовая политика: возобновить с того же места, если есть чекпоинт
        checkpoint = self.restore_from_checkpoint(task_id)
        if checkpoint:
            return {
                "action": "resume",
                "checkpoint": checkpoint,
                "delay": 0,
                "priority_boost": 1,
            }
        else:
            return {
                "action": "restart",
                "reason": "no_checkpoint",
                "delay": 5,
            }

    def _record_decision(self, decision: InterruptDecision):
        """Сохраняет решение в историю и публикует в workspace."""
        self.interrupt_history.append(decision)
        # Ограничиваем размер истории
        if len(self.interrupt_history) > 1000:
            self.interrupt_history.pop(0)

        # Публикация в workspace (если нужно)
        if self.workspace_service:
            self.workspace_service.publish_update(
                channel="interrupt_decisions",
                message=decision.to_dict(),
            )

        logger.info(
            f"Interrupt decision: {decision.should_interrupt} "
            f"(type: {decision.interrupt_type}, reason: {decision.reason}, priority: {decision.priority})"
        )

    def get_recent_decisions(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self.interrupt_history[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        """Статистика по прерываниям."""
        total = len(self.interrupt_history)
        positive = sum(1 for d in self.interrupt_history if d.should_interrupt)
        types = {}
        for d in self.interrupt_history:
            t = d.interrupt_type.value
            types[t] = types.get(t, 0) + 1
        return {
            "total_decisions": total,
            "interrupts_triggered": positive,
            "interrupt_rate": positive / total if total > 0 else 0,
            "by_type": types,
            "checkpoint_count": len(self.checkpoints),
        }


# Глобальный экземпляр
interrupt_manager = InterruptManager()


def get_interrupt_manager() -> InterruptManager:
    return interrupt_manager