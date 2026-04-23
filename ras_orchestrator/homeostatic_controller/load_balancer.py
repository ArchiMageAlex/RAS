"""
Балансировщик нагрузки для динамического масштабирования агентов и распределения задач.
"""

import logging
from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime, timedelta, UTC

logger = logging.getLogger(__name__)


class LoadBalancer:
    """Управляет балансировкой нагрузки между агентами."""

    def __init__(self, min_agents: int = 1, max_agents: int = 10):
        self.min_agents = min_agents
        self.max_agents = max_agents
        self.current_agents = min_agents
        self.agent_status: Dict[str, Dict[str, Any]] = {}  # agent_id -> status
        self.task_distribution: Dict[str, List[str]] = {}  # agent_id -> list of task_ids
        self.last_adjustment_time: Optional[datetime] = None
        self.adjustment_cooldown = timedelta(seconds=60)

    async def initialize(self):
        """Инициализация балансировщика."""
        logger.info(f"LoadBalancer initialized with {self.current_agents} agents.")

    async def shutdown(self):
        """Корректное завершение работы."""
        logger.info("LoadBalancer shut down.")

    async def adjust_agents(self, parameters: Dict[str, Any]) -> bool:
        """
        Корректирует количество агентов на основе параметров.
        Параметры могут включать:
          - delta: изменение количества (+/-)
          - target_count: целевое количество
          - agent_type: тип агента (например, "retriever")
        """
        if self.last_adjustment_time and (datetime.now(UTC) - self.last_adjustment_time) < self.adjustment_cooldown:
            logger.warning("Adjustment cooldown active, skipping.")
            return False

        delta = parameters.get("delta", 0)
        target_count = parameters.get("target_count")
        agent_type = parameters.get("agent_type", "retriever")

        if target_count is not None:
            new_count = max(self.min_agents, min(self.max_agents, target_count))
        else:
            new_count = self.current_agents + delta
            new_count = max(self.min_agents, min(self.max_agents, new_count))

        if new_count == self.current_agents:
            logger.debug("Agent count unchanged.")
            return True

        change = new_count - self.current_agents
        if change > 0:
            await self._scale_up(change, agent_type)
        else:
            await self._scale_down(-change, agent_type)

        self.current_agents = new_count
        self.last_adjustment_time = datetime.now(UTC)
        logger.info(f"Adjusted agents: {self.current_agents} (change: {change})")
        return True

    async def _scale_up(self, count: int, agent_type: str):
        """Запускает дополнительные агенты."""
        for i in range(count):
            agent_id = f"{agent_type}_{datetime.now(UTC).timestamp()}_{i}"
            self.agent_status[agent_id] = {
                "type": agent_type,
                "started_at": datetime.now(UTC),
                "status": "starting",
                "load": 0.0,
            }
            self.task_distribution[agent_id] = []
            logger.info(f"Agent {agent_id} started.")

    async def _scale_down(self, count: int, agent_type: str):
        """Останавливает агентов."""
        # Выбираем наименее загруженных агентов данного типа
        candidates = [
            (agent_id, status)
            for agent_id, status in self.agent_status.items()
            if status["type"] == agent_type and status["status"] == "idle"
        ]
        if len(candidates) < count:
            # Если недостаточно idle, выбираем с наименьшей нагрузкой
            candidates = sorted(
                [(agent_id, status) for agent_id, status in self.agent_status.items() if status["type"] == agent_type],
                key=lambda x: x[1]["load"]
            )

        for agent_id, _ in candidates[:count]:
            await self._stop_agent(agent_id)

    async def _stop_agent(self, agent_id: str):
        """Останавливает агента и перенаправляет его задачи."""
        if agent_id not in self.agent_status:
            return

        # Перенаправляем задачи на других агентов
        tasks = self.task_distribution.get(agent_id, [])
        if tasks:
            logger.warning(f"Agent {agent_id} has {len(tasks)} pending tasks, reassigning...")
            # Простая стратегия: распределить по другим агентам того же типа
            agent_type = self.agent_status[agent_id]["type"]
            other_agents = [
                aid for aid in self.agent_status.keys()
                if aid != agent_id and self.agent_status[aid]["type"] == agent_type
            ]
            if other_agents:
                for task_id in tasks:
                    target = other_agents[hash(task_id) % len(other_agents)]
                    self.task_distribution.setdefault(target, []).append(task_id)

        # Удаляем агента
        del self.agent_status[agent_id]
        del self.task_distribution[agent_id]
        logger.info(f"Agent {agent_id} stopped.")

    async def assign_task(self, task_id: str, task_type: str) -> Optional[str]:
        """
        Назначает задачу агенту с наименьшей нагрузкой.
        Возвращает ID агента или None, если нет доступных.
        """
        # Фильтруем агентов по типу и статусу
        candidates = [
            (agent_id, status)
            for agent_id, status in self.agent_status.items()
            if status["type"] == task_type and status["status"] in ("idle", "running")
        ]
        if not candidates:
            logger.warning(f"No agents available for task type {task_type}")
            return None

        # Выбираем агента с наименьшей нагрузкой
        candidates.sort(key=lambda x: x[1]["load"])
        agent_id, status = candidates[0]

        # Обновляем нагрузку
        self.agent_status[agent_id]["load"] += 0.1
        self.task_distribution.setdefault(agent_id, []).append(task_id)

        logger.debug(f"Task {task_id} assigned to agent {agent_id}")
        return agent_id

    async def complete_task(self, agent_id: str, task_id: str):
        """Отмечает задачу выполненной и снижает нагрузку агента."""
        if agent_id in self.agent_status:
            self.agent_status[agent_id]["load"] = max(0.0, self.agent_status[agent_id]["load"] - 0.1)
            if self.agent_status[agent_id]["load"] < 0.01:
                self.agent_status[agent_id]["status"] = "idle"

        if agent_id in self.task_distribution and task_id in self.task_distribution[agent_id]:
            self.task_distribution[agent_id].remove(task_id)

    async def throttle(self, parameters: Dict[str, Any]) -> bool:
        """
        Ограничивает поток событий (throttling).
        Параметры:
          - factor: множитель (0.0 - 1.0)
          - source: источник событий для ограничения
        """
        factor = parameters.get("factor", 0.5)
        source = parameters.get("source", "all")
        logger.info(f"Throttling {source} by factor {factor}")
        # В реальной реализации здесь было бы управление rate limiting
        return True

    async def get_status(self) -> Dict[str, Any]:
        """Возвращает статус балансировщика."""
        agent_counts = {}
        for status in self.agent_status.values():
            agent_type = status["type"]
            agent_counts[agent_type] = agent_counts.get(agent_type, 0) + 1

        total_load = sum(status["load"] for status in self.agent_status.values())
        avg_load = total_load / len(self.agent_status) if self.agent_status else 0.0

        return {
            "total_agents": self.current_agents,
            "agent_counts": agent_counts,
            "avg_load": avg_load,
            "pending_tasks": sum(len(tasks) for tasks in self.task_distribution.values()),
            "last_adjustment": self.last_adjustment_time.isoformat() if self.last_adjustment_time else None,
        }