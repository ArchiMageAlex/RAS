"""
Unit tests для расширенных алгоритмов оценки значимости (advanced_scoring).
"""
import pytest
import time
from unittest.mock import Mock, patch
from common.models import Event, EventType, Severity
from salience_engine.advanced_scoring import (
    AdvancedScoring,
    AnomalyDetector,
    SimilarityCache,
    ExternalContextClient,
)


def test_anomaly_detector():
    """Тест детектора аномалий."""
    detector = AnomalyDetector(window_size=5)
    # Обновляем статистику
    detector.update(0.5)
    detector.update(0.6)
    detector.update(0.55)
    detector.update(0.52)
    detector.update(0.58)
    # Нормальное значение
    is_anomaly, z = detector.detect(0.6)
    assert not is_anomaly
    # Аномальное значение
    is_anomaly, z = detector.detect(2.0)
    assert is_anomaly
    # Проверка статистики
    assert detector.stats["mean"] > 0.5
    assert detector.stats["std"] > 0


def test_similarity_cache():
    """Тест кэша похожих событий."""
    cache = SimilarityCache(max_size=2, ttl_seconds=1)
    event = Event(
        event_id="test-1",
        type=EventType.USER_COMPLAINT,
        severity=Severity.LOW,
        source="test",
        payload={"message": "hello"},
    )
    # Кэш пуст
    assert cache.get(event) is None
    # Сохраняем
    cache.set(event, 0.75)
    assert cache.get(event) == 0.75
    # Проверка TTL
    time.sleep(1.1)
    assert cache.get(event) is None  # истёк TTL
    # Проверка LRU вытеснения
    event2 = Event(
        event_id="test-2",
        type=EventType.SECURITY_ALERT,
        severity=Severity.HIGH,
        source="test",
        payload={"message": "alert"},
    )
    event3 = Event(
        event_id="test-3",
        type=EventType.PAYMENT_OUTAGE,
        severity=Severity.CRITICAL,
        source="test",
        payload={"message": "outage"},
    )
    cache.set(event, 0.1)
    cache.set(event2, 0.2)
    cache.set(event3, 0.3)  # должен вытеснить event (самый старый)
    assert cache.get(event) is None
    assert cache.get(event2) == 0.2
    assert cache.get(event3) == 0.3


def test_external_context_client():
    """Тест клиента внешнего контекста."""
    client = ExternalContextClient()
    event = Event(
        event_id="test",
        type=EventType.SYSTEM_HEALTH,
        severity=Severity.MEDIUM,
        source="test",
    )
    context = client.fetch_context(event)
    assert "related_incidents" in context
    assert "system_load" in context
    assert "time_of_day" in context
    assert "day_of_week" in context


def test_advanced_scoring_compute():
    """Тест вычисления расширенной оценки."""
    scoring = AdvancedScoring()
    event = Event(
        event_id="test-adv",
        type=EventType.SECURITY_ALERT,
        severity=Severity.HIGH,
        source="test",
        payload={"confidence": 0.9},
    )
    result = scoring.compute(event)
    assert "aggregated" in result
    assert 0.0 <= result["aggregated"] <= 1.0
    assert "relevance" in result
    assert "novelty" in result
    assert "risk" in result
    assert "urgency" in result
    assert "uncertainty" in result
    assert "weights" in result
    assert "is_anomaly" in result
    assert "z_score" in result
    assert "context" in result
    assert result["cached"] is False


def test_advanced_scoring_cache_hit():
    """Тест попадания в кэш."""
    scoring = AdvancedScoring()
    event = Event(
        event_id="test-cache",
        type=EventType.PERFORMANCE_DEGRADATION,
        severity=Severity.MEDIUM,
        source="test",
        payload={"confidence": 0.8},
    )
    # Симулируем кэш
    scoring.cache.set(event, 0.42)
    result = scoring.compute(event)
    assert result["cached"] is True
    assert result["aggregated"] == 0.42
    # Проверяем, что остальные поля могут отсутствовать или быть default
    assert "relevance" not in result  # в случае кэша только aggregated


def test_advanced_scoring_weights():
    """Тест весов для типов событий."""
    scoring = AdvancedScoring()
    weights = scoring.get_weights_for_event("security_alert")
    assert weights["risk"] == 0.4  # переопределено
    assert weights["urgency"] == 0.3
    assert weights["relevance"] == 0.2
    # Для неизвестного типа возвращаются default
    weights2 = scoring.get_weights_for_event("unknown")
    assert weights2 == scoring.default_weights


def test_compute_relevance():
    """Тест вычисления релевантности."""
    scoring = AdvancedScoring()
    event = Event(
        event_id="test",
        type=EventType.SECURITY_ALERT,
        severity=Severity.CRITICAL,
        source="test",
    )
    context = {"related_incidents": 3}
    relevance = scoring.compute_relevance(event, context)
    assert relevance == 1.0  # CRITICAL даёт 1.0, плюс бонус за related_incidents? (но ограничено min(1.0, base+0.2))
    # Проверка для LOW
    event2 = Event(
        event_id="test2",
        type=EventType.SYSTEM_HEALTH,
        severity=Severity.LOW,
        source="test",
    )
    relevance2 = scoring.compute_relevance(event2, context)
    assert 0.2 <= relevance2 <= 1.0


def test_compute_novelty():
    """Тест вычисления новизны."""
    scoring = AdvancedScoring()
    event = Event(
        event_id="test",
        type=EventType.SYSTEM_HEALTH,
        severity=Severity.MEDIUM,
        source="test",
    )
    context_night = {"time_of_day": 2}
    context_day = {"time_of_day": 14}
    novelty_night = scoring.compute_novelty(event, context_night)
    novelty_day = scoring.compute_novelty(event, context_day)
    assert novelty_night == 0.7
    assert novelty_day == 0.3


def test_compute_risk():
    """Тест вычисления риска."""
    scoring = AdvancedScoring()
    event = Event(
        event_id="test",
        type=EventType.SECURITY_ALERT,
        severity=Severity.HIGH,
        source="test",
    )
    context = {"system_load": 0.9}
    risk = scoring.compute_risk(event, context)
    # base_risk для security_alert = 0.9, плюс system_load*0.2 = 0.18, итого 1.08 -> ограничено 1.0
    assert risk == 1.0


def test_compute_urgency():
    """Тест вычисления срочности."""
    scoring = AdvancedScoring()
    event_critical = Event(
        event_id="test",
        type=EventType.PAYMENT_OUTAGE,
        severity=Severity.CRITICAL,
        source="test",
    )
    event_low = Event(
        event_id="test2",
        type=EventType.SYSTEM_HEALTH,
        severity=Severity.LOW,
        source="test",
    )
    context_weekday = {"day_of_week": 1}  # вторник
    context_weekend = {"day_of_week": 6}  # воскресенье
    urgency_critical = scoring.compute_urgency(event_critical, context_weekday)
    urgency_low = scoring.compute_urgency(event_low, context_weekday)
    urgency_critical_weekend = scoring.compute_urgency(event_critical, context_weekend)
    assert urgency_critical == 0.9
    assert urgency_low == 0.4
    assert urgency_critical_weekend == 0.9 * 0.8  # умножение на 0.8


def test_compute_uncertainty():
    """Тест вычисления неопределённости."""
    scoring = AdvancedScoring()
    event = Event(
        event_id="test",
        type=EventType.SYSTEM_HEALTH,
        severity=Severity.MEDIUM,
        source="test",
        payload={"confidence": 0.7},
    )
    context = {"system_load": 0.5}
    uncertainty = scoring.compute_uncertainty(event, context)
    # 1 - 0.7 = 0.3, плюс 0.5*0.1 = 0.05, итого 0.35
    assert abs(uncertainty - 0.35) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])