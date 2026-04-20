"""
Unit tests для Salience Engine.
"""
import pytest
from datetime import datetime
from common.models import Event, EventType, Severity
from salience_engine.engine import SalienceEngine, EnhancedSalienceEngine
from salience_engine.advanced_scoring import AdvancedScoring, SimilarityCache, AnomalyDetector


def test_salience_engine_basic():
    """Тест базового движка."""
    engine = SalienceEngine()
    event = Event(
        event_id="test-1",
        type=EventType.SECURITY_ALERT,
        severity=Severity.HIGH,
        source="test",
        payload={"confidence": 0.9},
    )
    score = engine.compute(event)
    assert 0.0 <= score.relevance <= 1.0
    assert 0.0 <= score.novelty <= 1.0
    assert 0.0 <= score.risk <= 1.0
    assert 0.0 <= score.urgency <= 1.0
    assert 0.0 <= score.uncertainty <= 1.0
    assert 0.0 <= score.aggregated <= 1.0
    # Для security_alert риск должен быть высоким
    assert score.risk > 0.5


def test_enhanced_salience_engine():
    """Тест улучшенного движка с кэшированием."""
    engine = EnhancedSalienceEngine(use_cache=True, use_anomaly_detection=False)
    event = Event(
        event_id="test-2",
        type=EventType.PAYMENT_OUTAGE,
        severity=Severity.CRITICAL,
        source="test",
        payload={"confidence": 0.8},
    )
    score1 = engine.compute(event)
    score2 = engine.compute(event)  # должен сработать кэш
    # Ожидаем, что aggregated одинаковый (кэширование)
    assert score1.aggregated == score2.aggregated


def test_advanced_scoring():
    """Тест расширенного scoring."""
    scoring = AdvancedScoring()
    event = Event(
        event_id="test-3",
        type=EventType.PERFORMANCE_DEGRADATION,
        severity=Severity.MEDIUM,
        source="test",
        payload={"confidence": 0.7},
    )
    result = scoring.compute(event)
    assert "aggregated" in result
    assert "relevance" in result
    assert "is_anomaly" in result
    assert 0.0 <= result["aggregated"] <= 1.0


def test_similarity_cache():
    """Тест кэша похожих событий."""
    cache = SimilarityCache(max_size=2, ttl_seconds=1)
    event = Event(
        event_id="test-4",
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
    import time
    time.sleep(1.1)
    assert cache.get(event) is None  # истёк TTL


def test_anomaly_detector():
    """Тест детектора аномалий."""
    detector = AnomalyDetector(window_size=5)
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])