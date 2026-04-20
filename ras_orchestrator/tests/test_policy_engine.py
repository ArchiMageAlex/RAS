"""
Unit tests для Policy Engine (обёртка).
"""
import pytest
from unittest.mock import Mock, patch
from common.models import Event, EventType, Severity, SalienceScore, SystemMode
from policy_engine.engine import PolicyEngine


def test_policy_engine_init():
    """Тест инициализации."""
    with patch('policy_engine.engine.PolicyEngineCore') as mock_core:
        engine = PolicyEngine(policy_dir="/some/dir", watch=True)
        mock_core.assert_called_once_with(policy_dir="/some/dir", watch=True)
        assert engine.core is mock_core.return_value


def test_evaluate_interrupt_policy():
    """Тест оценки политики прерывания."""
    mock_core = Mock()
    mock_core.evaluate_interrupt.return_value = {"should_interrupt": True}
    with patch('policy_engine.engine.PolicyEngineCore', return_value=mock_core):
        engine = PolicyEngine()
        event = Event(
            event_id="e1",
            type=EventType.SECURITY_ALERT,
            severity=Severity.HIGH,
            source="test"
        )
        score = SalienceScore(
            relevance=0.8,
            novelty=0.7,
            risk=0.9,
            urgency=0.8,
            uncertainty=0.2,
            aggregated=0.85
        )
        result = engine.evaluate_interrupt_policy(
            event, score, SystemMode.NORMAL, []
        )
        assert result == {"should_interrupt": True}
        mock_core.evaluate_interrupt.assert_called_once_with(
            event, score, SystemMode.NORMAL, []
        )


def test_evaluate_mode_policy():
    """Тест оценки политики режима."""
    mock_core = Mock()
    mock_core.evaluate_mode.return_value = {"new_mode": "elevated"}
    with patch('policy_engine.engine.PolicyEngineCore', return_value=mock_core):
        engine = PolicyEngine()
        score = SalienceScore(
            relevance=0.6,
            novelty=0.5,
            risk=0.7,
            urgency=0.6,
            uncertainty=0.3,
            aggregated=0.65
        )
        result = engine.evaluate_mode_policy(score)
        assert result == {"new_mode": "elevated"}
        mock_core.evaluate_mode.assert_called_once_with(score)


def test_matches_conditions_deprecated():
    """Тест устаревшего метода (заглушка)."""
    engine = PolicyEngine()
    with patch('policy_engine.engine.logger') as mock_logger:
        result = engine._matches_conditions({}, {})
        assert result is False
        mock_logger.warning.assert_called()


def test_global_instances():
    """Тест глобальных экземпляров."""
    from policy_engine.engine import policy_engine, get_policy_engine, get_core_engine
    assert isinstance(policy_engine, PolicyEngine)
    assert get_policy_engine() is policy_engine
    # get_core_engine возвращает PolicyEngineCore
    with patch('policy_engine.engine.get_global_engine') as mock_get:
        mock_core = Mock()
        mock_get.return_value = mock_core
        core = get_core_engine(watch=True)
        assert core is mock_core
        mock_get.assert_called_with(watch=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])