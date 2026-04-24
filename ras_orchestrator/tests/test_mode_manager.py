"""
Unit tests для Mode Manager.
"""
import pytest
from datetime import datetime, timedelta
from common.models import SystemMode, SalienceScore, SystemMetrics
from mode_manager.manager import ModeManager, ModeTransitionReason


def test_mode_manager_initial():
    """Тест инициализации."""
    manager = ModeManager(initial_mode=SystemMode.NORMAL)
    assert manager.get_current_mode() == SystemMode.NORMAL
    assert len(manager.get_history()) == 0


def test_evaluate_salience_low():
    """Тест оценки низкой значимости."""
    manager = ModeManager(initial_mode=SystemMode.NORMAL)
    score = SalienceScore(
        relevance=0.1,
        novelty=0.1,
        risk=0.1,
        urgency=0.1,
        uncertainty=0.1,
        aggregated=0.15,  # ниже порога LOW (0.2)
    )
    new_mode = manager.evaluate(score)
    assert new_mode == SystemMode.LOW
    assert manager.get_current_mode() == SystemMode.LOW
    history = manager.get_history()
    assert len(history) == 1
    assert history[0]["from"] == SystemMode.NORMAL
    assert history[0]["to"] == SystemMode.LOW


def test_evaluate_salience_critical():
    """Тест оценки критической значимости."""
    manager = ModeManager(initial_mode=SystemMode.NORMAL)
    score = SalienceScore(
        relevance=0.9,
        novelty=0.9,
        risk=0.9,
        urgency=0.9,
        uncertainty=0.1,
        aggregated=0.95,  # выше порога CRITICAL (0.9)
    )
    new_mode = manager.evaluate(score)
    assert new_mode == SystemMode.CRITICAL
    assert manager.get_current_mode() == SystemMode.CRITICAL


def test_hysteresis():
    """Тест гистерезиса (разные пороги для повышения и понижения)."""
    manager = ModeManager(
        initial_mode=SystemMode.NORMAL,
        hysteresis_up=0.1,
        hysteresis_down=0.05,
    )
    # Порог для elevated = 0.7 + 0.1 = 0.8 (повышение)
    score_elevated = SalienceScore(
        aggregated=0.85,  # выше порога elevated
        relevance=0.5,
        novelty=0.5,
        risk=0.5,
        urgency=0.5,
        uncertainty=0.5,
    )
    new_mode = manager.evaluate(score_elevated)
    assert new_mode == SystemMode.ELEVATED

    # Теперь aggregated падает до 0.75, что всё ещё выше базового порога 0.7,
    # но из-за гистерезиса понижения (0.7 - 0.05 = 0.65) мы остаёмся в elevated
    score_normal = SalienceScore(aggregated=0.75, **{k: 0.5 for k in ["relevance", "novelty", "risk", "urgency", "uncertainty"]})
    new_mode = manager.evaluate(score_normal)
    assert new_mode == SystemMode.ELEVATED  # остаётся


def test_system_metrics_adjustment():
    """Тест корректировки порогов на основе системных метрик."""
    manager = ModeManager()
    metrics = SystemMetrics(
        cpu_load=0.9,  # высокая нагрузка
        latency_ms=200,
        error_rate=0.3,
        queue_depth=10,
    )
    manager.update_system_metrics(metrics)
    # При высокой нагрузке пороги должны снизиться
    adjusted = manager._adjust_thresholds()
    assert adjusted[SystemMode.ELEVATED] < 0.7  # исходный порог 0.7
    assert adjusted[SystemMode.CRITICAL] < 0.9


def test_cooldown_after_critical():
    """Тест cooldown после critical режима."""
    manager = ModeManager(initial_mode=SystemMode.CRITICAL)
    # Выходим из critical
    manager.set_mode_manually(SystemMode.NORMAL)
    assert manager.get_current_mode() == SystemMode.NORMAL
    # Попытка вернуться в critical должна быть заблокирована cooldown
    score = SalienceScore(aggregated=0.99, **{k: 0.9 for k in ["relevance", "novelty", "risk", "urgency", "uncertainty"]})
    new_mode = manager.evaluate(score)
    # Должен остаться normal или elevated, но не critical
    assert new_mode != SystemMode.CRITICAL


def test_manual_lock():
    """Тест блокировки ручного переключения."""
    manager = ModeManager()
    manager.set_mode_manually(SystemMode.ELEVATED, lock=True)
    assert manager.get_current_mode() == SystemMode.ELEVATED
    assert manager.manual_lock is True
    # Автоматическая оценка должна игнорироваться
    score = SalienceScore(aggregated=0.2, **{k: 0.1 for k in ["relevance", "novelty", "risk", "urgency", "uncertainty"]})
    new_mode = manager.evaluate(score)
    assert new_mode == SystemMode.ELEVATED  # не изменился
    # Снимаем блокировку
    manager.release_manual_lock()
    assert manager.manual_lock is False
    new_mode = manager.evaluate(score)
    assert new_mode == SystemMode.LOW  # теперь изменился


if __name__ == "__main__":
    pytest.main([__file__, "-v"])