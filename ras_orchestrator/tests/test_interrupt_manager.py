"""
Unit tests для Interrupt Manager.
"""
import pytest
from datetime import datetime
from common.models import Event, EventType, Severity, SystemMode, SalienceScore, Task
from interrupt_manager.manager import (
    InterruptManager,
    InterruptDecision,
    InterruptType,
    TaskCheckpoint,
)


def test_interrupt_decision():
    """Тест создания решения о прерывании."""
    decision = InterruptDecision(
        should_interrupt=True,
        reason="test",
        interrupt_type=InterruptType.SOFT,
        priority=5,
        delay_seconds=10,
        checkpoint_required=True,
    )
    assert decision.should_interrupt is True
    assert decision.reason == "test"
    assert decision.interrupt_type == InterruptType.SOFT
    assert decision.priority == 5
    assert decision.delay_seconds == 10
    assert decision.checkpoint_required is True
    dict_repr = decision.to_dict()
    assert dict_repr["should_interrupt"] is True
    assert dict_repr["interrupt_type"] == "soft"


def test_interrupt_manager_no_active_tasks():
    """Тест, когда нет активных задач - прерывание не требуется."""
    manager = InterruptManager()
    event = Event(
        event_id="test-1",
        type=EventType.SECURITY_ALERT,
        severity=Severity.HIGH,
        source="test",
    )
    score = SalienceScore(
        relevance=0.9,
        novelty=0.9,
        risk=0.9,
        urgency=0.9,
        uncertainty=0.1,
        aggregated=0.95,
    )
    decision = manager.evaluate(event, score, SystemMode.NORMAL, [])
    assert decision.should_interrupt is False
    assert decision.reason == "no_active_tasks"


def test_interrupt_manager_high_salience():
    """Тест прерывания при высокой значимости."""
    manager = InterruptManager()
    event = Event(
        event_id="test-2",
        type=EventType.PAYMENT_OUTAGE,
        severity=Severity.CRITICAL,
        source="test",
    )
    score = SalienceScore(
        relevance=0.8,
        novelty=0.8,
        risk=0.8,
        urgency=0.8,
        uncertainty=0.2,
        aggregated=0.85,  # > 0.8
    )
    task = Task(task_id="task-1", event_id="test-2", agent_type="test")
    decision = manager.evaluate(event, score, SystemMode.NORMAL, [task])
    assert decision.should_interrupt is True
    assert decision.reason == "high_salience"
    assert decision.interrupt_type == InterruptType.SOFT
    assert decision.checkpoint_required is True


def test_interrupt_manager_critical_mode_high_risk():
    """Тест прерывания в критическом режиме с высоким риском."""
    manager = InterruptManager()
    event = Event(
        event_id="test-3",
        type=EventType.SECURITY_ALERT,
        severity=Severity.CRITICAL,
        source="test",
    )
    score = SalienceScore(
        relevance=0.7,
        novelty=0.7,
        risk=0.8,  # > 0.7
        urgency=0.7,
        uncertainty=0.3,
        aggregated=0.75,
    )
    task = Task(task_id="task-2", event_id="test-3", agent_type="test")
    decision = manager.evaluate(event, score, SystemMode.CRITICAL, [task])
    # Ожидаем hard interrupt из-за critical mode high risk
    assert decision.should_interrupt is True
    assert decision.reason == "critical_mode_high_salience"
    assert decision.interrupt_type == InterruptType.HARD


def test_checkpoint_creation():
    """Тест создания чекпоинтов."""
    manager = InterruptManager()
    tasks = [
        Task(task_id="task-1", event_id="e1", agent_type="test"),
        Task(task_id="task-2", event_id="e2", agent_type="test"),
    ]
    manager._create_checkpoints(tasks)
    # Чекпоинты должны быть в памяти
    assert len(manager.checkpoints) == 2
    assert "task-1" in manager.checkpoints
    assert "task-2" in manager.checkpoints


def test_restore_from_checkpoint():
    """Тест восстановления из чекпоинта."""
    manager = InterruptManager()
    task = Task(task_id="task-3", event_id="e3", agent_type="test")
    manager._create_checkpoints([task])
    checkpoint_data = manager.restore_from_checkpoint("task-3")
    assert checkpoint_data is not None
    assert checkpoint_data["task"]["task_id"] == "task-3"
    # Восстановление несуществующего чекпоинта
    assert manager.restore_from_checkpoint("nonexistent") is None


def test_resumption_policy():
    """Тест политики возобновления."""
    manager = InterruptManager()
    task = Task(task_id="task-4", event_id="e4", agent_type="test")
    manager._create_checkpoints([task])
    policy = manager.get_resumption_policy("task-4")
    assert policy["action"] == "resume"
    assert "checkpoint" in policy
    # Для задачи без чекпоинта
    policy = manager.get_resumption_policy("no-task")
    assert policy["action"] == "restart"
    assert policy["reason"] == "no_checkpoint"


def test_stats():
    """Тест статистики."""
    manager = InterruptManager()
    event = Event(
        event_id="test-4",
        type=EventType.SYSTEM_HEALTH,
        severity=Severity.MEDIUM,
        source="test",
    )
    score = SalienceScore(
        relevance=0.5,
        novelty=0.5,
        risk=0.5,
        urgency=0.5,
        uncertainty=0.5,
        aggregated=0.5,
    )
    task = Task(task_id="task-5", event_id="test-4", agent_type="test")
    manager.evaluate(event, score, SystemMode.NORMAL, [task])
    stats = manager.get_stats()
    assert stats["total_decisions"] == 1
    assert stats["interrupts_triggered"] == 0  # aggregated=0.5 не вызывает прерывание
    assert "by_type" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])