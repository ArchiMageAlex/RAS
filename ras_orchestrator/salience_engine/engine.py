import logging
import os
import time
from typing import Dict, Any, Optional
from contextlib import nullcontext
from common.models import Event, SalienceScore, Severity
from common.telemetry import get_tracer, business_metrics, system_metrics
from .advanced_scoring import AdvancedScoring, SimilarityCache, AnomalyDetector
from .novelty_detector import NoveltyDetector
from .historical_repository import HistoricalRepository
from .trust_scorer import TrustScorer
from .source_registry import SourceRegistry

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

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        historical_repository: Optional[HistoricalRepository] = None,
        novelty_detector: Optional[NoveltyDetector] = None,
        source_registry: Optional[SourceRegistry] = None,
        trust_scorer: Optional[TrustScorer] = None,
    ):
        # Веса для агрегации (можно настраивать)
        self.weights = weights or {
            "relevance": 0.3,
            "novelty": 0.2,
            "risk": 0.25,
            "urgency": 0.15,
            "uncertainty": 0.1,
        }
        self.historical_repository = historical_repository
        self.novelty_detector = novelty_detector
        self.source_registry = source_registry
        self.trust_scorer = trust_scorer

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

    def _get_trust_score(self, source: str) -> float:
        """Возвращает trust score источника (0.0-1.0)."""
        if self.trust_scorer and self.source_registry:
            try:
                return self.trust_scorer.compute_trust(source)
            except Exception as e:
                logger.warning(f"Trust scoring failed for source {source}: {e}")
        return 0.5  # нейтральное значение по умолчанию

    def _compute_relevance(self, event: Event) -> float:
        """Релевантность события целям системы с учётом trust score."""
        severity_map = {
            Severity.LOW: 0.2,
            Severity.MEDIUM: 0.5,
            Severity.HIGH: 0.8,
            Severity.CRITICAL: 1.0,
        }
        base = severity_map.get(event.severity, 0.5)
        trust = self._get_trust_score(event.source)
        # Корректировка: доверенные источники увеличивают релевантность, ненадёжные уменьшают
        # trust = 0.5 → множитель 1.0, trust = 1.0 → множитель 1.2, trust = 0.0 → множитель 0.8
        multiplier = 0.8 + (trust * 0.4)
        return max(0.0, min(1.0, base * multiplier))

    def _compute_novelty(self, event: Event) -> float:
        """Новизна события на основе исторических паттернов."""
        if self.novelty_detector and self.historical_repository:
            try:
                return self.novelty_detector.compute_novelty(event)
            except Exception as e:
                logger.warning(f"Novelty detection failed: {e}, falling back to default")
                return 0.3
        # Если детектор не настроен, возвращаем значение по умолчанию
        return 0.3

    def _compute_risk(self, event: Event) -> float:
        """Риск события с учётом trust score."""
        if event.type == "security_alert":
            base = 0.9
        elif event.type == "payment_outage":
            base = 0.8
        else:
            base = 0.4

        trust = self._get_trust_score(event.source)
        # Корректировка: ненадёжные источники увеличивают риск, доверенные уменьшают
        # trust = 0.0 → множитель 1.3, trust = 1.0 → множитель 0.7
        multiplier = 1.3 - (trust * 0.6)
        return max(0.0, min(1.0, base * multiplier))

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