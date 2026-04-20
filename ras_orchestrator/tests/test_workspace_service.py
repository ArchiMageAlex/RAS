"""
Unit tests для Workspace Service.
"""
import pytest
import json
from unittest.mock import Mock, patch
from workspace_service.redis_client import WorkspaceService


def test_workspace_service_init():
    """Тест инициализации."""
    with patch('redis.Redis') as mock_redis:
        service = WorkspaceService(host='test', port=9999, db=1)
        assert service.prefix == "ras:workspace:"
        mock_redis.assert_called_once_with(
            host='test', port=9999, db=1, decode_responses=True
        )


def test_key_generation():
    """Тест генерации ключей."""
    service = WorkspaceService()
    key = service._key("event", "123")
    assert key == "ras:workspace:event:123"


def test_store_event():
    """Тест сохранения события."""
    mock_redis = Mock()
    with patch('workspace_service.redis_client.redis.Redis', return_value=mock_redis):
        service = WorkspaceService()
        event = {"event_id": "e1", "data": "test"}
        service.store_event(event)
        mock_redis.set.assert_called_once_with(
            "ras:workspace:event:e1",
            json.dumps(event, default=str)
        )
        mock_redis.expire.assert_not_called()
        # С TTL
        service.store_event(event, ttl=60)
        assert mock_redis.expire.called


def test_get_event():
    """Тест получения события."""
    mock_redis = Mock()
    with patch('workspace_service.redis_client.redis.Redis', return_value=mock_redis):
        service = WorkspaceService()
        event = {"event_id": "e1", "data": "test"}
        mock_redis.get.return_value = json.dumps(event)
        result = service.get_event("e1")
        assert result == event
        mock_redis.get.assert_called_with("ras:workspace:event:e1")
        # Не найдено
        mock_redis.get.return_value = None
        result = service.get_event("nonexistent")
        assert result is None


def test_store_salience_score():
    """Тест сохранения salience score."""
    mock_redis = Mock()
    with patch('workspace_service.redis_client.redis.Redis', return_value=mock_redis):
        service = WorkspaceService()
        score = {"aggregated": 0.8}
        service.store_salience_score("e1", score)
        mock_redis.set.assert_called_with(
            "ras:workspace:salience:e1",
            json.dumps(score, default=str)
        )


def test_get_salience_score():
    """Тест получения salience score."""
    mock_redis = Mock()
    with patch('workspace_service.redis_client.redis.Redis', return_value=mock_redis):
        service = WorkspaceService()
        score = {"aggregated": 0.8}
        mock_redis.get.return_value = json.dumps(score)
        result = service.get_salience_score("e1")
        assert result == score


def test_set_mode():
    """Тест установки режима."""
    mock_redis = Mock()
    with patch('workspace_service.redis_client.redis.Redis', return_value=mock_redis):
        service = WorkspaceService()
        service.set_mode("critical")
        mock_redis.set.assert_called_with("ras:workspace:system:mode", "critical")


def test_get_mode():
    """Тест получения режима."""
    mock_redis = Mock()
    with patch('workspace_service.redis_client.redis.Redis', return_value=mock_redis):
        service = WorkspaceService()
        mock_redis.get.return_value = "elevated"
        assert service.get_mode() == "elevated"
        # Если None, возвращает "normal"
        mock_redis.get.return_value = None
        assert service.get_mode() == "normal"


def test_add_active_task():
    """Тест добавления активной задачи."""
    mock_redis = Mock()
    with patch('workspace_service.redis_client.redis.Redis', return_value=mock_redis):
        service = WorkspaceService()
        task_data = {"task_id": "t1", "status": "running"}
        service.add_active_task("t1", task_data)
        mock_redis.hset.assert_called_with(
            "ras:workspace:tasks:active",
            "t1",
            json.dumps(task_data, default=str)
        )


def test_remove_active_task():
    """Тест удаления активной задачи."""
    mock_redis = Mock()
    with patch('workspace_service.redis_client.redis.Redis', return_value=mock_redis):
        service = WorkspaceService()
        service.remove_active_task("t1")
        mock_redis.hdel.assert_called_with("ras:workspace:tasks:active", "t1")


def test_get_active_tasks():
    """Тест получения активных задач."""
    mock_redis = Mock()
    with patch('workspace_service.redis_client.redis.Redis', return_value=mock_redis):
        service = WorkspaceService()
        task_data = {"task_id": "t1", "status": "running"}
        mock_redis.hgetall.return_value = {"t1": json.dumps(task_data)}
        tasks = service.get_active_tasks()
        assert tasks == {"t1": task_data}


def test_publish_update():
    """Тест публикации обновления."""
    mock_redis = Mock()
    with patch('workspace_service.redis_client.redis.Redis', return_value=mock_redis):
        service = WorkspaceService()
        message = {"update": "test"}
        service.publish_update("channel1", message)
        mock_redis.publish.assert_called_with(
            "channel1",
            json.dumps(message, default=str)
        )


def test_health():
    """Тест проверки здоровья."""
    mock_redis = Mock()
    with patch('workspace_service.redis_client.redis.Redis', return_value=mock_redis):
        service = WorkspaceService()
        mock_redis.ping.return_value = True
        assert service.health() is True
        mock_redis.ping.side_effect = Exception("error")
        assert service.health() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])