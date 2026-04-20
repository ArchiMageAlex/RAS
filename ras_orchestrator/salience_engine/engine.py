import logging
import os
import time
from typing import Dict, Any, Optional
from contextlib import nullcontext
from common.models import Event, SalienceScore, Severity
from common.telemetry import get_tracer, business_metrics, system_metrics
from .advanced_scoring import AdvancedScoring, SimilarityCache, AnomalyDetector

logger = logging.getLogger(__name__)
tracer = get_tracer("salience_engine")


class SafeTracer:
    """Safe tracer wrapper that works when OpenTelemetry is not available."""
    
    def start_as_current_span(self, name: str, **kwargs):
        """Return a null context if tracer is not available."""
        if tracer is not None:
            return tracer.start_as_current_span(name, **kwargs)
        return nullcontext()


class SalienceEngine:
    """Базовый двигатель оценки значимости событий (обратная совместимость)."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        # Веса для агрегации (можно настраивать)
        self.weights = weights or {
            "relevance": 0.3,
            "novelty": 0.2,
            "risk": 0.25,
            "urgency": 0.15,
            "uncertainty": 0.1,
        }

    def compute(self, event: Event) -> SalienceScore:
        """Вычисляет salience score для события."""
        safe_tracer = SafeTracer()
        with safe_tracer.start_as_current_span("salience_compute") as span:
            if span:
                span.set_attribute("event.id", event.event_id)
                span.set_attribute("event.type", event.type.value)
                span.set_attribute("event.severity", event.severity.value)

            start_time = time.time()
            relevance = self._compute_relevance(event)
            novelty = self._compute_novelty(event)
            risk = self._compute_risk(event)
            urgency = self._compute_urgency(event)
            uncertainty = self._compute_uncertainty(event)

            aggregated = (
                relevance * self.weights["relevance"]
                + novelty * self.weights["novelty"]
                + risk * self.weights["risk"]
                + urgency * self.weights["urgency"]
                + uncertainty * self.weights["uncertainty"]
            )

            score = SalienceScore(
                relevance=relevance,
                novelty=novelty,
                risk=risk,
                urgency=urgency,
                uncertainty=uncertainty,
                aggregated=aggregated,
            )
            elapsed = (time.time() - start_time) * 1000  # milliseconds
            if span:
                span.set_attribute("computation.time_ms", elapsed)
                span.set_attribute("salience.score", aggregated)

            # Record metrics
            business_metrics["salience_score_distribution"].record(aggregated)
            system_metrics["service_error_rate"].add(0)  # placeholder

            logger.info(f"Computed salience score for event {event.event_id}: {aggregated:.3f}")
            return score

    def _compute_relevance(self, event: Event) -> float:
        """Релевантность события целям системы."""
        severity_map = {
            Severity.LOW: 0.2,
            Severity.MEDIUM: 0.5,
            Severity.HIGH: 0.8,
            Severity.CRITICAL: 1.0,
        }
        return severity_map.get(event.severity, 0.5)

    def _compute_novelty(self, event: Event) -> float:
        """Новизна события (пока заглушка)."""
        return 0.3

    def _compute_risk(self, event: Event) -> float:
        """Риск события."""
        if event.type == "security_alert":
            return 0.9
        if event.type == "payment_outage":
            return 0.8
        return 0.4

    def _compute_urgency(self, event: Event) -> float:
        """Срочность."""
        if event.severity in [Severity.HIGH, Severity.CRITICAL]:
            return 0.9
        return 0.4

    def _compute_uncertainty(self, event: Event) -> float:
        """Неопределённость (обратная уверенности)."""
        confidence = event.payload.get("confidence", 0.8)
        return 1.0 - confidence


class EnhancedSalienceEngine(SalienceEngine):
    """
    Улучшенный движок с кэшированием, ML-аномалиями, внешним контекстом
    и конфигурируемыми весами по типам событий.
    """

    def __init__(
        self,
        use_cache: bool = True,
        use_anomaly_detection: bool = True,
        use_external_context: bool = False,
        default_weights: Optional[Dict[str, float]] = None,
        event_type_weights: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        super().__init__(weights=default_weights)
        self.use_cache = use_cache
        self.use_anomaly_detection = use_anomaly_detection
        self.use_external_context = use_external_context

        self.cache = SimilarityCache() if use_cache else None
        self.anomaly_detector = AnomalyDetector() if use_anomaly_detection else None
        self.advanced_scoring = AdvancedScoring(
            default_weights=default_weights,
            event_type_weights=event_type_weights,
        )

    def compute(self, event: Event) -> SalienceScore:
        """Вычисляет salience score с улучшенными возможностями."""
        safe_tracer = SafeTracer()
        with safe_tracer.start_as_current_span("enhanced_salience_compute") as span:
            if span:
                span.set_attribute("event.id", event.event_id)
                span.set_attribute("cache.enabled", self.use_cache)
                span.set_attribute("anomaly_detection.enabled", self.use_anomaly_detection)

            # Проверка кэша
            if self.use_cache and self.cache:
                cached = self.cache.get(event)
                if cached is not None:
                    logger.debug(f"Cache hit for event {event.event_id}")
                    if span:
                        span.set_attribute("cache.hit", True)
                    # Возвращаем стандартный SalienceScore с кэшированным aggregated
                    # Для остальных компонентов используем значения по умолчанию (можно улучшить)
                    return SalienceScore(
                        relevance=0.5,
                        novelty=0.3,
                        risk=0.4,
                        urgency=0.4,
                        uncertainty=0.2,
                        aggregated=cached,
                    )
                if span:
                    span.set_attribute("cache.hit", False)

            # Используем расширенное вычисление
            result = self.advanced_scoring.compute(event)

            # Детекция аномалий (логирование)
            if self.use_anomaly_detection and self.anomaly_detector:
                is_anomaly, z_score = self.anomaly_detector.detect(result["aggregated"])
                if is_anomaly:
                    logger.warning(
                        f"Anomalous salience score detected for event {event.event_id}: "
                        f"score={result['aggregated']:.3f}, z={z_score:.2f}"
                    )
                    if span:
                        span.set_attribute("anomaly.detected", True)
                        span.set_attribute("anomaly.z_score", z_score)
                    business_metrics["interrupt_rate"].add(1, {"type": "anomaly_detected"})

            # Сохранение в кэш
            if self.use_cache and self.cache:
                self.cache.set(event, result["aggregated"])

            # Преобразование в SalienceScore
            score = SalienceScore(
                relevance=result["relevance"],
                novelty=result["novelty"],
                risk=result["risk"],
                urgency=result["urgency"],
                uncertainty=result["uncertainty"],
                aggregated=result["aggregated"],
            )
            logger.info(
                f"Computed enhanced salience score for event {event.event_id}: "
                f"{result['aggregated']:.3f} (anomaly: {result.get('is_anomaly', False)})"
            )
            # Record metric
            business_metrics["salience_score_distribution"].record(result["aggregated"])
            return score


# Конфигурация движка через переменные окружения
ENGINE_TYPE = os.getenv("SALIENCE_ENGINE_TYPE", "enhanced").lower()

# Глобальные экземпляры
_base_engine = SalienceEngine()
_enhanced_engine = EnhancedSalienceEngine(
    use_cache=True,
    use_anomaly_detection=True,
    use_external_context=False,
)

def get_salience_engine() -> SalienceEngine:
    """Возвращает движок в зависимости от конфигурации."""
    if ENGINE_TYPE == "enhanced":
        return _enhanced_engine
    else:
        return _base_engine

# Глобальный экземпляр для обратной совместимости
engine = get_salience_engine()