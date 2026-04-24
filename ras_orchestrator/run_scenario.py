#!/usr/bin/env python3
"""
End-to-end сценарий для демонстрации работы RAS-like оркестратора.
Имитирует событие payment_outage с high severity.
"""
import asyncio
import logging
import sys
from datetime import datetime

sys.path.insert(0, '.')

from common.models import Event, EventType, Severity, SystemMode, Task
from common.utils import setup_logging, EVENT_COUNTER, SALIENCE_SCORE_HISTOGRAM
from salience_engine.engine import SalienceEngine
from mode_manager.manager import ModeManager
from common.models import SystemMetrics
from interrupt_manager.manager import InterruptManager
from task_orchestrator.orchestrator import TaskOrchestrator
from workspace_service.redis_client import WorkspaceService

logger = logging.getLogger(__name__)


async def run_scenario():
    """Запускает end-to-end сценарий."""
    setup_logging()
    logger.info("=== Начало end-to-end сценария ===")

    # Инициализация компонентов
    salience_engine = SalienceEngine()
    mode_manager = ModeManager()
    interrupt_manager = InterruptManager()
    task_orchestrator = TaskOrchestrator()
    workspace = WorkspaceService()

    try:
        # 1. Создание события payment_outage
        event = Event(
            event_id="test_payment_outage_001",
            type=EventType.PAYMENT_OUTAGE,
            severity=Severity.CRITICAL,
            source="payment_service",
            payload={
                "service": "payment_gateway",
                "region": "eu-west-1",
                "error_rate": 0.95,
                "confidence": 0.9,
            },
            metadata={"simulated": True},
        )
        logger.info(f"Создано событие: {event.event_id} ({event.type.value}, {event.severity.value})")
        EVENT_COUNTER.labels(event_type=event.type.value, severity=event.severity.value).inc()

        # 2. Оценка значимости (Salience Engine)
        salience_score = salience_engine.compute(event)
        logger.info(f"Salience score: {salience_score.aggregated:.3f}")
        SALIENCE_SCORE_HISTOGRAM.observe(salience_score.aggregated)

        # 3. Определение режима (Mode Manager)
        # Опционально можно передать системные метрики
        system_metrics = SystemMetrics(
            cpu_load=0.7,
            latency_ms=150.0,
            error_rate=0.1,
            queue_depth=25,
        )
        current_mode = mode_manager.evaluate(salience_score, system_metrics=system_metrics)
        logger.info(f"Текущий режим системы: {current_mode.value}")

        # 4. Проверка прерывания (Interrupt Manager)
        active_tasks: list[Task] = []  # Нет активных задач
        decision = interrupt_manager.evaluate(
            event=event,
            salience_score=salience_score,
            current_mode=current_mode,
            active_tasks=active_tasks,
        )
        logger.info(f"Решение о прерывании: {decision.should_interrupt} (причина: {decision.reason})")

        # 5. Создание задачи (Task Orchestrator)
        task = task_orchestrator.create_task(event, task_type="retrieval")
        logger.info(f"Создана задача: {task.task_id}")

        # 6. Назначение агенту и выполнение
        success = task_orchestrator.assign_agent(task)
        logger.info(f"Задача выполнена: {success}, результат: {task.result}")

        # 7. Сохранение в workspace
        workspace.store_event(event.model_dump(mode='json'))
        workspace.store_salience_score(event.event_id, salience_score.model_dump(mode='json'))
        workspace.set_mode(current_mode.value)
        logger.info("Данные сохранены в workspace.")

        # 8. Итог
        logger.info("=== Сценарий завершён ===")
        print("\n--- Итоги ---")
        print(f"Событие: {event.event_id}")
        print(f"Salience score: {salience_score.aggregated:.3f}")
        print(f"Режим системы: {current_mode.value}")
        print(f"Прерывание: {'ДА' if decision.should_interrupt else 'НЕТ'}")
        print(f"Задача: {task.task_id} ({task.status})")
        print(f"Результат агента: {task.result.get('summary', 'N/A') if task.result else 'N/A'}")

    except redis.ConnectionError as e:
        logger.error(f"Redis connection error: {e}")
        logger.warning("Сценарий продолжен без сохранения в workspace.")
        print("\n--- Итоги (без workspace) ---")
        print(f"Событие: {event.event_id}")
        print(f"Salience score: {salience_score.aggregated:.3f}")
        print(f"Режим системы: {current_mode.value}")
        print(f"Прерывание: {'ДА' if decision.should_interrupt else 'НЕТ'}")
        print(f"Задача: {task.task_id} ({task.status})")
    except Exception as e:
        logger.error(f"Ошибка выполнения сценария: {e}")
        raise


if __name__ == "__main__":
    import redis
    asyncio.run(run_scenario())