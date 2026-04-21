"""
Unit tests для компонентов Phase 2 Adaptive Attention.
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, patch
from common.models import Event, EventType, Severity, HistoricalEvent, Task, TaskCheckpoint, SourceTrust
from salience_engine.novelty_detector import NoveltyDetector
from salience_engine.historical_repository import HistoricalRepository
from salience_engine.trust_scorer import TrustScorer
from salience_engine.source_registry import SourceRegistry
from task_orchestrator.checkpoint_manager import CheckpointManager
from task_orchestrator.serialization import StateSerializer, Checkpointable
from human_escalation.escalation_manager import EscalationManager
from human_escalation.workflow_engine import WorkflowEngine
from human_escalation.models import EscalationWorkflow, EscalationStep, EscalationAction


def test_novelty_detector_basic():
    """Тест детектора новизны."""
    repo = Mock(spec=HistoricalRepository)
    repo.get_events_in_window.return_value = [
        HistoricalEvent(event_id="hist1", type=EventType.SECURITY_ALERT, severity=Severity.MEDIUM,
                        source="source1", timestamp=datetime.utcnow(), payload={}),
        HistoricalEvent(event_id="hist2", type=EventType.SECURITY_ALERT, severity=Severity.HIGH,
                        source="source2", timestamp=datetime.utcnow(), payload={}),
    ]
    detector = NoveltyDetector(historical_repository=repo)
    event = Event(
        event_id="test-1",
        type=EventType.SECURITY_ALERT,
        severity=Severity.HIGH,
        source="source1",
        payload={"confidence": 0.9},
    )
    novelty = detector.compute_novelty(event)
    assert 0.0 <= novelty <= 1.0
    # При наличии похожих событий новизна должна быть меньше 1.0
    assert novelty < 1.0
    repo.get_events_in_window.assert_called_once()


def test_novelty_detector_no_history():
    """Тест детектора новизны при отсутствии истории."""
    repo = Mock(spec=HistoricalRepository)
    repo.get_events_in_window.return_value = []
    detector = NoveltyDetector(historical_repository=repo)
    event = Event(
        event_id="test-2",
        type=EventType.PAYMENT_OUTAGE,
        severity=Severity.CRITICAL,
        source="new_source",
        payload={},
    )
    novelty = detector.compute_novelty(event)
    # Если нет истории, новизна должна быть высокой (близкой к 1.0)
    assert novelty > 0.8
    repo.get_events_in_window.assert_called_once()


def test_trust_scorer_basic():
    """Тест оценки доверия к источнику."""
    registry = Mock(spec=SourceRegistry)
    registry.get_or_create.return_value = SourceTrust(
        source="source_a",
        trust_score=0.85,
        events_count=100,
        accuracy=0.85,
        last_updated=datetime.utcnow()
    )
    scorer = TrustScorer(source_registry=registry)
    trust = scorer.compute_trust("source_a")
    assert 0.0 <= trust <= 1.0
    # При высокой точности доверие должно быть > 0.5
    assert trust > 0.5
    registry.get_or_create.assert_called_once_with("source_a")


def test_trust_scorer_unknown_source():
    """Тест оценки доверия для неизвестного источника."""
    registry = Mock(spec=SourceRegistry)
    registry.get_or_create.return_value = SourceTrust(
        source="unknown_source",
        trust_score=0.3,
        events_count=0,
        accuracy=1.0,
        last_updated=datetime.utcnow()
    )
    scorer = TrustScorer(source_registry=registry)
    trust = scorer.compute_trust("unknown_source")
    # Для неизвестного источника доверие должно быть низким (по умолчанию 0.3)
    assert trust == 0.3
    registry.get_or_create.assert_called_once_with("unknown_source")


def test_checkpoint_manager_save_and_load():
    """Тест сохранения и загрузки чекпоинта."""
    import json
    workspace = Mock()
    workspace.store_checkpoint.return_value = True
    agent_state = {"step": 5, "data": "sample"}
    # Сериализуем состояние, как это делает StateSerializer для JSON
    serialized = json.dumps(agent_state).encode('utf-8')
    workspace.get_checkpoint.return_value = serialized
    manager = CheckpointManager(workspace=workspace)
    task = Task(task_id="task_123", event_id="event_1", agent_type="retrieval")
    checkpoint_id = manager.save_checkpoint(task, agent_state, ttl_seconds=3600, format="json")
    assert checkpoint_id is not None
    assert checkpoint_id.startswith("cp_")
    workspace.store_checkpoint.assert_called_once()
    # Загрузка
    loaded = manager.load_checkpoint(checkpoint_id, format="json")
    assert loaded is not None
    loaded_task, loaded_state = loaded
    assert loaded_state == agent_state
    workspace.get_checkpoint.assert_called_once_with(checkpoint_id)


def test_checkpoint_manager_invalid_format():
    """Тест обработки неверного формата сериализации."""
    workspace = Mock()
    manager = CheckpointManager(workspace=workspace)
    task = Task(task_id="task1", event_id="event1", agent_type="retrieval")
    with pytest.raises(ValueError):
        manager.save_checkpoint(task, {"a": 1}, format="invalid")


def test_escalation_manager_evaluate():
    """Тест оценки эскалации менеджером."""
    policy_engine = Mock()
    policy_engine.evaluate_escalation_policy.return_value = {
        "should_escalate": True,
        "escalation_level": "high",
        "notify_channels": ["slack"],
        "timeout_seconds": 300,
        "policy_name": "test_policy",
    }
    workflow_engine = Mock()
    workflow_engine.start_workflow.return_value = Mock(instance_id="inst_123", status="running")
    manager = EscalationManager(policy_engine=policy_engine, workflow_engine=workflow_engine)
    event = Event(
        event_id="event_1",
        type=EventType.SECURITY_ALERT,
        severity=Severity.CRITICAL,
        source="test",
    )
    salience_score = {"relevance": 0.9, "risk": 0.8}
    instance = manager.evaluate_and_escalate(event, salience_score)
    assert instance is not None
    assert instance.instance_id == "inst_123"
    policy_engine.evaluate_escalation_policy.assert_called_once()
    workflow_engine.start_workflow.assert_called_once()


def test_escalation_manager_no_escalation():
    """Тест, когда эскалация не требуется."""
    policy_engine = Mock()
    policy_engine.evaluate_escalation_policy.return_value = {"should_escalate": False}
    manager = EscalationManager(policy_engine=policy_engine)
    event = Event(
        event_id="event_2",
        type=EventType.SYSTEM_HEALTH,
        severity=Severity.LOW,
        source="test",
    )
    salience_score = {"relevance": 0.2, "risk": 0.1}
    instance = manager.evaluate_and_escalate(event, salience_score)
    assert instance is None


def test_workflow_engine_start():
    """Тест запуска workflow."""
    workspace = Mock()
    workspace.redis_client = Mock()
    workspace.redis_client.set = Mock()
    engine = WorkflowEngine(workspace=workspace)
    workflow = EscalationWorkflow(
        workflow_id="wf1",
        trigger_policy="test",
        steps=[
            EscalationStep(action=EscalationAction.NOTIFY, parameters={"message": "test"}),
        ],
    )
    event = Event(event_id="e1", type=EventType.SYSTEM_HEALTH, severity=Severity.LOW, source="test")
    instance = engine.start_workflow(workflow, event, {})
    assert instance.instance_id.startswith("escalation_")
    assert instance.workflow_id == "wf1"
    # После выполнения единственного шага NOTIFY workflow завершается
    assert instance.status == "completed"
    # Проверяем, что сохранение в workspace было вызвано
    assert workspace.redis_client.set.called


def test_state_serializer_json():
    """Тест сериализатора JSON."""
    serializer = StateSerializer()
    data = {"key": "value", "number": 42}
    serialized = serializer.serialize(data, format="json")
    assert isinstance(serialized, bytes)
    deserialized = serializer.deserialize(serialized, format="json")
    assert deserialized == data


def test_state_serializer_pickle():
    """Тест сериализатора pickle."""
    serializer = StateSerializer()
    data = {"key": "value", "list": [1, 2, 3]}
    serialized = serializer.serialize(data, format="pickle")
    assert isinstance(serialized, bytes)
    deserialized = serializer.deserialize(serialized, format="pickle")
    assert deserialized == data


def test_checkpointable_interface():
    """Тест интерфейса Checkpointable."""
    class DummyAgent(Checkpointable):
        def __init__(self):
            self.state = {"counter": 0}
        def get_state(self):
            return self.state
        def set_state(self, state):
            self.state = state

    agent = DummyAgent()
    agent.set_state({"counter": 5})
    assert agent.get_state()["counter"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])