"""
End-to-end integration tests для полного workflow RAS-like оркестратора.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from common.models import Event, EventType, Severity, SalienceScore, SystemMode, Task
from salience_engine.engine import SalienceEngine
from mode_manager.manager import ModeManager
from interrupt_manager.manager import InterruptManager, InterruptDecision
from task_orchestrator.orchestrator import TaskOrchestrator
from workspace_service.redis_client import WorkspaceService


def test_full_workflow_with_mocks():
    """
    Тест полного workflow с моками всех внешних зависимостей.
    Шаги:
      1. Создание события payment_outage
      2. Оценка значимости (Salience Engine)
      3. Определение режима (Mode Manager)
      4. Проверка прерывания (Interrupt Manager)
      5. Создание задачи (Task Orchestrator)
      6. Назначение агенту и выполнение
      7. Сохранение в workspace
    """
    # Мокируем Redis, Kafka, внешние API
    with patch('workspace_service.redis_client.redis.Redis') as mock_redis_class, \
         patch('task_orchestrator.orchestrator.RetrieverAgent') as mock_agent_class, \
         patch('salience_engine.engine.SalienceEngine._load_ml_model'):
        # Настраиваем моки
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis.hset.return_value = True
        mock_redis.hgetall.return_value = {}

        mock_agent = Mock()
        mock_agent.execute.return_value = {"success": True, "summary": "Retrieved data"}
        mock_agent_class.return_value = mock_agent

        # 1. Создание события
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

        # 2. Оценка значимости
        salience_engine = SalienceEngine()
        salience_score = salience_engine.compute(event)
        assert isinstance(salience_score, SalienceScore)
        assert 0.0 <= salience_score.aggregated <= 1.0
        # Для CRITICAL PAYMENT_OUTAGE ожидаем высокий aggregated
        assert salience_score.aggregated > 0.7

        # 3. Определение режима
        mode_manager = ModeManager()
        current_mode = mode_manager.evaluate(salience_score)
        assert current_mode in SystemMode
        # При высоком aggregated должен быть elevated или critical
        if salience_score.aggregated > 0.8:
            assert current_mode in [SystemMode.ELEVATED, SystemMode.CRITICAL]

        # 4. Проверка прерывания
        interrupt_manager = InterruptManager()
        active_tasks = []  # нет активных задач
        decision = interrupt_manager.evaluate(event, salience_score, current_mode, active_tasks)
        assert isinstance(decision, InterruptDecision)
        # При высокой значимости и отсутствии задач прерывание не требуется
        # (но в логике InterruptManager может быть should_interrupt = False)
        # Проверяем, что решение принято
        assert decision.reason is not None

        # 5. Создание задачи
        workspace = WorkspaceService()
        task_orchestrator = TaskOrchestrator(workspace=workspace)
        task = task_orchestrator.create_task(event, task_type="retrieval")
        assert isinstance(task, Task)
        assert task.event_id == event.event_id
        assert task.agent_type == "retrieval"
        assert task.status == "created"
        # Проверяем, что задача добавлена в workspace
        assert workspace.add_active_task.called

        # 6. Назначение агенту и выполнение
        success = task_orchestrator.assign_agent(task)
        assert success is True
        assert task.status == "completed"
        assert task.result == {"success": True, "summary": "Retrieved data"}
        # Проверяем, что агент был вызван
        mock_agent.execute.assert_called_once_with(task)
        # Задача должна быть удалена из активных
        assert workspace.remove_active_task.called

        # 7. Сохранение в workspace
        workspace.store_event.assert_called()
        workspace.store_salience_score.assert_called()
        workspace.set_mode.assert_called_with(current_mode.value)

        # Итог: все шаги выполнены без исключений
        print("Workflow тест пройден успешно.")


def test_workflow_with_active_tasks_interrupt():
    """
    Тест workflow с активными задачами, которые должны быть прерваны.
    """
    with patch('workspace_service.redis_client.redis.Redis') as mock_redis_class, \
         patch('salience_engine.engine.SalienceEngine._load_ml_model'):
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis
        mock_redis.get.return_value = None
        mock_redis.hgetall.return_value = {}

        event = Event(
            event_id="test_security_alert",
            type=EventType.SECURITY_ALERT,
            severity=Severity.CRITICAL,
            source="security",
            payload={"confidence": 0.95},
        )
        salience_engine = SalienceEngine()
        salience_score = salience_engine.compute(event)
        mode_manager = ModeManager()
        current_mode = mode_manager.evaluate(salience_score)

        # Создаём активную задачу
        active_task = Task(
            task_id="active_task_1",
            event_id="previous_event",
            agent_type="retrieval",
            status="running",
        )
        interrupt_manager = InterruptManager()
        decision = interrupt_manager.evaluate(event, salience_score, current_mode, [active_task])
        # При высокой значимости и наличии активных задач должно быть прерывание
        if salience_score.aggregated > 0.8:
            assert decision.should_interrupt is True
            assert decision.interrupt_type in ["soft", "hard"]


def test_error_handling_in_workflow():
    """
    Тест обработки ошибок в workflow (например, падение агента).
    """
    with patch('workspace_service.redis_client.redis.Redis') as mock_redis_class, \
         patch('task_orchestrator.orchestrator.RetrieverAgent') as mock_agent_class:
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis
        mock_redis.hgetall.return_value = {}

        mock_agent = Mock()
        mock_agent.execute.return_value = {"success": False, "error": "timeout"}
        mock_agent_class.return_value = mock_agent

        event = Event(
            event_id="test_failure",
            type=EventType.SYSTEM_HEALTH,
            severity=Severity.MEDIUM,
            source="test",
        )
        workspace = WorkspaceService()
        task_orchestrator = TaskOrchestrator(workspace=workspace)
        task = task_orchestrator.create_task(event, task_type="retrieval")
        success = task_orchestrator.assign_agent(task)
        assert success is False
        assert task.status == "failed"
        assert task.result == {"success": False, "error": "timeout"}
        # Задача должна быть удалена из активных (перемещена в failed)
        assert workspace.remove_active_task.called


def test_kafka_integration_mock():
    """
    Тест интеграции с Kafka (мок).
    """
    from integration.coordinator import IntegrationCoordinator
    with patch('integration.coordinator.KafkaProducer') as mock_producer_class:
        mock_producer = Mock()
        mock_future = Mock()
        mock_future.get.return_value = Mock(partition=0, offset=123)
        mock_producer.send.return_value = mock_future
        mock_producer_class.return_value = mock_producer

        coordinator = IntegrationCoordinator()
        coordinator.redis = Mock()
        coordinator.redis.get.return_value = None

        event = Event(
            event_id="test_kafka",
            type=EventType.USER_COMPLAINT,
            severity=Severity.LOW,
            source="test",
        )
        result = coordinator.send_event_with_idempotency(event, idempotency_key="key1")
        assert result["success"] is True
        assert result["partition"] == 0
        assert result["offset"] == 123
        mock_producer.send.assert_called_once()


def test_redis_workspace_synchronization():
    """
    Тест синхронизации workspace через Redis.
    """
    with patch('workspace_service.redis_client.redis.Redis') as mock_redis_class:
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis
        mock_redis.get.return_value = None
        mock_redis.hgetall.return_value = {}

        workspace = WorkspaceService()
        event = {"event_id": "e1", "data": "test"}
        workspace.store_event(event)
        mock_redis.set.assert_called()
        # Проверяем, что ключ содержит префикс
        call_args = mock_redis.set.call_args[0]
        assert call_args[0].startswith("ras:workspace:event:")

        # Получение события
        mock_redis.get.return_value = '{"event_id": "e1", "data": "test"}'
        retrieved = workspace.get_event("e1")
        assert retrieved == event


if __name__ == "__main__":
    pytest.main([__file__, "-v"])