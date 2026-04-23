"""
Основной контроллер гомеостаза, поддерживающий стабильность системы через регулировку нагрузки и ресурсов.
Использует PID-регулятор и правила для корректировки параметров системы.
"""

import logging
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from common.models import SystemMetrics, ControlAction, HomeostaticState
from .metrics_collector import MetricsCollector
from .load_balancer import LoadBalancer
from .priority_manager import PriorityManager
from .resource_allocator import ResourceAllocator

logger = logging.getLogger(__name__)


@dataclass
class TargetRange:
    """Целевой диапазон для метрики."""
    min: float
    max: float
    weight: float = 1.0  # вес при вычислении отклонения


class HomeostaticController:
    """Контроллер гомеостаза системы."""

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        load_balancer: Optional[LoadBalancer] = None,
        priority_manager: Optional[PriorityManager] = None,
        resource_allocator: Optional[ResourceAllocator] = None,
        update_interval_seconds: int = 30,
    ):
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.load_balancer = load_balancer or LoadBalancer()
        self.priority_manager = priority_manager or PriorityManager()
        self.resource_allocator = resource_allocator or ResourceAllocator()
        self.update_interval = update_interval_seconds
        self.last_update_time: Optional[datetime] = None

        # Целевые диапазоны метрик (можно настраивать)
        self.target_ranges: Dict[str, TargetRange] = {
            "cpu_load": TargetRange(min=0.2, max=0.8, weight=1.5),
            "latency_ms": TargetRange(min=0.0, max=200.0, weight=2.0),
            "error_rate": TargetRange(min=0.0, max=0.01, weight=3.0),
            "queue_depth": TargetRange(min=0, max=50, weight=1.0),
            "memory_usage": TargetRange(min=0.0, max=0.85, weight=1.2),
        }

        # PID коэффициенты (для каждой метрики можно свои)
        self.pid_coefficients: Dict[str, Tuple[float, float, float]] = {
            "cpu_load": (0.8, 0.05, 0.1),
            "latency_ms": (1.0, 0.1, 0.2),
            "error_rate": (2.0, 0.2, 0.3),
        }

        # История ошибок для PID
        self.error_history: Dict[str, List[float]] = {}
        self.last_errors: Dict[str, float] = {}

        # Текущее состояние
        self.current_state: Optional[HomeostaticState] = None
        self.active_actions: List[ControlAction] = []

    async def initialize(self):
        """Инициализация контроллера."""
        await self.metrics_collector.initialize()
        logger.info("HomeostaticController initialized.")

    async def shutdown(self):
        """Корректное завершение работы."""
        await self.metrics_collector.shutdown()
        logger.info("HomeostaticController shut down.")

    async def update(self) -> HomeostaticState:
        """
        Основной цикл обновления: сбор метрик, вычисление отклонений, генерация действий.
        Возвращает текущее состояние гомеостаза.
        """
        now = datetime.now(UTC)
        if self.last_update_time and (now - self.last_update_time).total_seconds() < self.update_interval:
            # Пропускаем обновление, если не прошёл интервал
            return self.current_state

        # 1. Сбор метрик
        metrics = await self.metrics_collector.collect_all()
        system_metrics = SystemMetrics(
            cpu_load=metrics.get("cpu_load", 0.0),
            latency_ms=metrics.get("latency_ms", 0.0),
            error_rate=metrics.get("error_rate", 0.0),
            queue_depth=metrics.get("queue_depth", 0),
            memory_usage=metrics.get("memory_usage", 0.0),
            throughput=metrics.get("throughput", 0.0),
        )

        # 2. Вычисление отклонений
        deviations = self._compute_deviations(metrics)
        total_deviation = sum(d * self.target_ranges[metric].weight for metric, d in deviations.items())

        # 3. Генерация корректирующих действий
        actions = await self._generate_control_actions(metrics, deviations)

        # 4. Применение действий
        for action in actions:
            await self._execute_action(action)

        # 5. Обновление состояния
        self.current_state = HomeostaticState(
            timestamp=now,
            metrics=metrics,
            target_ranges={k: (v.min, v.max) for k, v in self.target_ranges.items()},
            current_actions=actions,
            deviation_score=total_deviation,
        )

        self.last_update_time = now
        logger.info(f"Homeostatic update completed. Deviation: {total_deviation:.3f}, actions: {len(actions)}")
        return self.current_state

    def _compute_deviations(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """Вычисляет отклонения метрик от целевых диапазонов."""
        deviations = {}
        for metric, value in metrics.items():
            if metric not in self.target_ranges:
                continue
            target = self.target_ranges[metric]
            if target.min <= value <= target.max:
                deviation = 0.0
            elif value < target.min:
                deviation = (target.min - value) / (target.min + 1e-6)
            else:  # value > target.max
                deviation = (value - target.max) / (target.max + 1e-6)
            deviations[metric] = deviation
        return deviations

    async def _generate_control_actions(
        self, metrics: Dict[str, float], deviations: Dict[str, float]
    ) -> List[ControlAction]:
        """Генерирует корректирующие действия на основе отклонений."""
        actions = []

        # Правила для каждой метрики
        for metric, deviation in deviations.items():
            if deviation == 0:
                continue

            # Выбор действия в зависимости от метрики
            if metric == "cpu_load" and deviation > 0.2:
                actions.append(ControlAction(
                    component="task_orchestrator",
                    action_type="scale_agents",
                    parameters={"delta": -1 if deviation < 0 else 1, "agent_type": "retriever"},
                ))
                actions.append(ControlAction(
                    component="mode_manager",
                    action_type="adjust_mode",
                    parameters={"adjustment": "higher" if deviation > 0 else "lower"},
                ))

            elif metric == "latency_ms" and deviation > 0.3:
                actions.append(ControlAction(
                    component="load_balancer",
                    action_type="throttle",
                    parameters={"factor": 0.8, "source": "high_latency"},
                ))
                actions.append(ControlAction(
                    component="priority_manager",
                    action_type="increase_priority",
                    parameters={"queue": "critical", "factor": 1.5},
                ))

            elif metric == "error_rate" and deviation > 0.5:
                actions.append(ControlAction(
                    component="mode_manager",
                    action_type="switch_mode",
                    parameters={"target_mode": "elevated"},
                ))
                actions.append(ControlAction(
                    component="human_escalation",
                    action_type="notify",
                    parameters={"level": "warning", "metric": "error_rate"},
                ))

            elif metric == "queue_depth" and deviation > 0.4:
                actions.append(ControlAction(
                    component="task_orchestrator",
                    action_type="scale_agents",
                    parameters={"delta": 2, "agent_type": "retriever"},
                ))

        # Ограничение количества одновременных действий
        if len(actions) > 5:
            actions = actions[:5]

        return actions

    async def _execute_action(self, action: ControlAction) -> bool:
        """Выполняет одно корректирующее действие через соответствующий компонент."""
        try:
            if action.component == "task_orchestrator":
                await self.load_balancer.adjust_agents(action.parameters)
            elif action.component == "load_balancer":
                await self.load_balancer.throttle(action.parameters)
            elif action.component == "priority_manager":
                await self.priority_manager.adjust_priorities(action.parameters)
            elif action.component == "mode_manager":
                # Интеграция с Mode Manager (заглушка)
                logger.info(f"Would adjust mode with params: {action.parameters}")
            elif action.component == "human_escalation":
                logger.info(f"Would notify humans: {action.parameters}")
            else:
                logger.warning(f"Unknown component: {action.component}")
                return False

            self.active_actions.append(action)
            logger.debug(f"Action executed: {action.component}.{action.action_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to execute action {action}: {e}")
            return False

    async def get_status(self) -> Dict[str, Any]:
        """Возвращает текущий статус контроллера."""
        if not self.current_state:
            return {"status": "uninitialized"}
        return {
            "status": "active",
            "last_update": self.last_update_time.isoformat() if self.last_update_time else None,
            "deviation_score": self.current_state.deviation_score,
            "active_actions_count": len(self.active_actions),
            "metrics": self.current_state.metrics,
        }

    def adjust_target_ranges(self, new_ranges: Dict[str, Tuple[float, float]]):
        """Динамическая корректировка целевых диапазонов."""
        for metric, (min_val, max_val) in new_ranges.items():
            if metric in self.target_ranges:
                self.target_ranges[metric].min = min_val
                self.target_ranges[metric].max = max_val
                logger.info(f"Adjusted target range for {metric}: [{min_val}, {max_val}]")

