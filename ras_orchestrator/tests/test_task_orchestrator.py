"""
Unit tests для Task Orchestrator.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from common.models import Event, EventType, Severity, Task
from task_orchestrator.orchestrator import TaskOrchestrator


def test_task_orchestrator_init():
    """Тест инициализации."""
    mock_workspace = Mock()
    orchestrator = TaskOrchestrator(workspace=mock_workspace)
    assert orchestrator.workspace == mock_workspace
    assert orchestrator.retriever_agent is not None


def test_create_task():
    """Тест создания задачи."""
    mock_workspace = Mock()
    orchestrator = TaskOrchestrator(workspace=mock_workspace)
    event = Event(
        event_id="e1",
        type=EventType.SECURITY_ALERT,
        severity=Severity.HIGH,
        source="test"
    )
    task = orchestrator.create_task(event, task_type="retrieval")
    assert task.task_id.startswith("task_")
    assert task.event_id == "e1"
    assert task.agent_type == "retrieval"
    assert task.status == "created"
    assert task.parameters["event_type"] == "security_alert"
    # Проверяем, что задача добавлена в workspace
    mock_workspace.add_active_task.assert_called_once_with(
        task.task_id, task.dict()
    )


def test_assign_agent_retrieval_success():
    """Тест назначения агента retrieval с успешным выполнением."""
    mock_workspace = Mock()
    mock_agent = Mock()
    mock_agent.execute.return_value = {"success": True, "data": "result"}
    with patch('task_orchestrator.orchestrator.RetrieverAgent', return_value=mock_agent):
        orchestrator = TaskOrchestrator(workspace=mock_workspace)
        task = Task(
            task_id="t1",
            event_id="e1",
            agent_type="retrieval",
            status="created"
        )
        result = orchestrator.assign_agent(task)
        assert result is True
        assert task.status == "completed"
        assert task.result == {"success": True, "data": "result"}
        # Проверяем обновление в workspace
        mock_workspace.add_active_task.assert_called_with("t1", task.dict())
        mock_workspace.remove_active_task.assert_called_with("t1")


def test_assign_agent_retrieval_failure():
    """Тест назначения агента retrieval с неудачей."""
    mock_workspace = Mock()
    mock_agent = Mock()
    mock_agent.execute.return_value = {"success": False, "error": "timeout"}
    with patch('task_orchestrator.orchestrator.RetrieverAgent', return_value=mock_agent):
        orchestrator = TaskOrchestrator(workspace=mock_workspace)
        task = Task(
            task_id="t1",
            event_id="e1",
            agent_type="retrieval",
            status="created"
        )
        result = orchestrator.assign_agent(task)
        assert result is False
        assert task.status == "failed"
        assert task.result == {"success": False, "error": "timeout"}
        mock_workspace.remove_active_task.assert_called_with("t1")


def test_assign_agent_unknown_type():
    """Тест назначения неизвестного типа агента."""
    mock_workspace = Mock()
    orchestrator = TaskOrchestrator(workspace=mock_workspace)
    task = Task(
        task_id="t1",
        event_id="e1",
        agent_type="unknown",
        status="created"
    )
    result = orchestrator.assign_agent(task)
    assert result is False
    assert task.status == "failed"
    assert task.result == {"error": "unknown_agent_type"}
    mock_workspace.remove_active_task.assert_called_with("t1")


def test_get_active_tasks():
    """Тест получения активных задач."""
    mock_workspace = Mock()
    mock_workspace.get_active_tasks.return_value = {
        "t1": {"task_id": "t1", "status": "running"},
        "t2": {"task_id": "t2", "status": "pending"}
    }
    orchestrator = TaskOrchestrator(workspace=mock_workspace)
    tasks = orchestrator.get_active_tasks()
    assert len(tasks) == 2
    assert tasks[0]["task_id"] == "t1"
    assert tasks[1]["task_id"] == "t2"


def test_cancel_task_exists():
    """Тест отмены существующей задачи."""
    mock_workspace = Mock()
    mock_workspace.get_active_tasks.return_value = {"t1": {}}
    orchestrator = TaskOrchestrator(workspace=mock_workspace)
    result = orchestrator.cancel_task("t1")
    assert result is True
    mock_workspace.remove_active_task.assert_called_with("t1")


def test_cancel_task_not_exists():
    """Тест отмены несуществующей задачи."""
    mock_workspace = Mock()
    mock_workspace.get_active_tasks.return_value = {}
    orchestrator = TaskOrchestrator(workspace=mock_workspace)
    result = orchestrator.cancel_task("t1")
    assert result is False
    mock_workspace.remove_active_task.assert_not_called()


def test_global_instance():
    """Тест глобального экземпляра."""
    from task_orchestrator.orchestrator import task_orchestrator, get_task_orchestrator
    assert isinstance(task_orchestrator, TaskOrchestrator)
    assert get_task_orchestrator() is task_orchestrator


if __name__ == "__main__":
    pytest.main([__file__, "-v"])