"""
Распределитель ресурсов между компонентами системы на основе приоритетов и доступности.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, UTC
from enum import Enum

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Типы ресурсов системы."""
    CPU = "cpu"
    MEMORY = "memory"
    NETWORK = "network"
    DISK_IO = "disk_io"
    AGENT_SLOTS = "agent_slots"


class ResourceAllocator:
    """Управляет распределением ресурсов между компонентами."""

    def __init__(self, total_resources: Optional[Dict[ResourceType, float]] = None):
        # Общее количество ресурсов (нормированное)
        self.total_resources = total_resources or {
            ResourceType.CPU: 1.0,          # 100% CPU
            ResourceType.MEMORY: 1.0,       # 100% памяти
            ResourceType.NETWORK: 1.0,      # 100% сетевой пропускной способности
            ResourceType.DISK_IO: 1.0,      # 100% IO
            ResourceType.AGENT_SLOTS: 10.0, # максимальное количество агентов
        }

        # Текущее распределение
        self.allocations: Dict[str, Dict[ResourceType, float]] = {
            "task_orchestrator": {
                ResourceType.CPU: 0.3,
                ResourceType.MEMORY: 0.4,
                ResourceType.AGENT_SLOTS: 5.0,
            },
            "salience_engine": {
                ResourceType.CPU: 0.2,
                ResourceType.MEMORY: 0.2,
            },
            "predictive_engine": {
                ResourceType.CPU: 0.1,
                ResourceType.MEMORY: 0.1,
            },
            "rl_agent": {
                ResourceType.CPU: 0.05,
                ResourceType.MEMORY: 0.05,
            },
            "homeostatic_controller": {
                ResourceType.CPU: 0.05,
                ResourceType.MEMORY: 0.05,
            },
        }

        # История распределения
        self.allocation_history: List[Dict[str, Any]] = []
        self.last_rebalance = datetime.now(UTC)

    async def initialize(self):
        """Инициализация распределителя."""
        logger.info("ResourceAllocator initialized.")

    async def shutdown(self):
        """Корректное завершение работы."""
        logger.info("ResourceAllocator shut down.")

    async def allocate(
        self,
        component: str,
        resources: Dict[ResourceType, float],
        priority: int = 1
    ) -> bool:
        """
        Выделяет ресурсы компоненту.
        Возвращает True, если выделение успешно.
        """
        # Проверяем доступность ресурсов
        for res_type, amount in resources.items():
            available = self._get_available(res_type)
            if amount > available:
                logger.warning(
                    f"Insufficient {res_type.value} for {component}: "
                    f"requested {amount}, available {available}"
                )
                return False

        # Выделяем ресурсы
        for res_type, amount in resources.items():
            self.allocations.setdefault(component, {})[res_type] = \
                self.allocations.get(component, {}).get(res_type, 0.0) + amount

        logger.info(f"Allocated resources to {component}: {resources}")
        self._record_allocation(component, resources, "allocate")
        return True

    async def deallocate(
        self,
        component: str,
        resources: Dict[ResourceType, float]
    ) -> bool:
        """Освобождает ресурсы, выделенные компоненту."""
        if component not in self.allocations:
            logger.warning(f"Component {component} has no allocations.")
            return False

        for res_type, amount in resources.items():
            current = self.allocations[component].get(res_type, 0.0)
            if amount > current:
                logger.warning(
                    f"Cannot deallocate more {res_type.value} than allocated: "
                    f"requested {amount}, allocated {current}"
                )
                # Освобождаем только то, что есть
                amount = current

            self.allocations[component][res_type] = current - amount
            if self.allocations[component][res_type] < 0.001:
                del self.allocations[component][res_type]

        # Если компонент больше не использует ресурсы, удаляем его запись
        if not self.allocations[component]:
            del self.allocations[component]

        logger.info(f"Deallocated resources from {component}: {resources}")
        self._record_allocation(component, resources, "deallocate")
        return True

    def _get_available(self, res_type: ResourceType) -> float:
        """Возвращает количество доступных ресурсов данного типа."""
        total = self.total_resources.get(res_type, 0.0)
        allocated = sum(
            alloc.get(res_type, 0.0)
            for alloc in self.allocations.values()
        )
        return max(0.0, total - allocated)

    async def rebalance_based_on_load(self, load_metrics: Dict[str, float]):
        """
        Перераспределяет ресурсы на основе текущей нагрузки.
        load_metrics может содержать:
          - cpu_load_by_component
          - memory_usage_by_component
          - queue_depths
        """
        # Простая стратегия: увеличиваем ресурсы компонентам с высокой нагрузкой
        cpu_load = load_metrics.get("cpu_load", 0.5)
        memory_pressure = load_metrics.get("memory_usage", 0.5)

        # Определяем, какие компоненты нуждаются в дополнительных ресурсах
        # (в реальной системе здесь был бы более сложный анализ)
        adjustments = {}

        if cpu_load > 0.8:
            # Перераспределяем CPU от фоновых компонентов к критическим
            adjustments["task_orchestrator"] = {ResourceType.CPU: 0.1}
            adjustments["predictive_engine"] = {ResourceType.CPU: -0.05}
            adjustments["rl_agent"] = {ResourceType.CPU: -0.05}

        if memory_pressure > 0.9:
            adjustments["task_orchestrator"] = adjustments.get("task_orchestrator", {})
            adjustments["task_orchestrator"][ResourceType.MEMORY] = 0.1
            adjustments["salience_engine"] = {ResourceType.MEMORY: -0.05}

        # Применяем корректировки
        for component, changes in adjustments.items():
            for res_type, delta in changes.items():
                current = self.allocations.get(component, {}).get(res_type, 0.0)
                new_amount = max(0.0, current + delta)
                if new_amount != current:
                    self.allocations.setdefault(component, {})[res_type] = new_amount
                    logger.debug(
                        f"Rebalanced {res_type.value} for {component}: "
                        f"{current:.2f} -> {new_amount:.2f}"
                    )

        self.last_rebalance = datetime.now(UTC)
        logger.info("Resource rebalancing completed based on load.")

    async def get_component_resources(self, component: str) -> Dict[str, float]:
        """Возвращает ресурсы, выделенные компоненту."""
        alloc = self.allocations.get(component, {})
        return {rt.value: amount for rt, amount in alloc.items()}

    async def get_system_resource_status(self) -> Dict[str, Any]:
        """Возвращает общий статус ресурсов системы."""
        available = {}
        allocated = {}
        utilization = {}

        for res_type, total in self.total_resources.items():
            alloc = sum(
                a.get(res_type, 0.0) for a in self.allocations.values()
            )
            avail = total - alloc
            available[res_type.value] = avail
            allocated[res_type.value] = alloc
            utilization[res_type.value] = alloc / total if total > 0 else 0.0

        return {
            "total_resources": {rt.value: v for rt, v in self.total_resources.items()},
            "allocated": allocated,
            "available": available,
            "utilization": utilization,
            "last_rebalance": self.last_rebalance.isoformat(),
            "components": {
                comp: {rt.value: amt for rt, amt in alloc.items()}
                for comp, alloc in self.allocations.items()
            },
        }

    def _record_allocation(
        self,
        component: str,
        resources: Dict[ResourceType, float],
        action: str
    ):
        """Записывает действие в историю."""
        self.allocation_history.append({
            "timestamp": datetime.now(UTC),
            "component": component,
            "action": action,
            "resources": {rt.value: amt for rt, amt in resources.items()},
            "total_allocations": {
                comp: {rt.value: amt for rt, amt in alloc.items()}
                for comp, alloc in self.allocations.items()
            },
        })
        # Ограничиваем размер истории
        if len(self.allocation_history) > 1000:
            self.allocation_history = self.allocation_history[-1000:]