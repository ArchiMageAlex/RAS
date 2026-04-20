import logging
from typing import Dict, Any
from common.models import Event, SalienceScore, Severity

logger = logging.getLogger(__name__)


class SalienceEngine:
    """Двигатель оценки значимости событий."""

    def __init__(self):
        # Веса для агрегации (можно настраивать)
        self.weights = {
            "relevance": 0.3,
            "novelty": 0.2,
            "risk": 0.25,
            "urgency": 0.15,
            "uncertainty": 0.1,
        }

    def compute(self, event: Event) -> SalienceScore:
        """Вычисляет salience score для события."""
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
        logger.info(f"Computed salience score for event {event.event_id}: {aggregated:.3f}")
        return score

    def _compute_relevance(self, event: Event) -> float:
        """Релевантность события целям системы."""
        # Заглушка: считаем, что события с high severity более релевантны
        severity_map = {
            Severity.LOW: 0.2,
            Severity.MEDIUM: 0.5,
            Severity.HIGH: 0.8,
            Severity.CRITICAL: 1.0,
        }
        return severity_map.get(event.severity, 0.5)

    def _compute_novelty(self, event: Event) -> float:
        """Новизна события (пока заглушка)."""
        # В реальности можно использовать историю событий
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
        # Зависит от severity и типа
        if event.severity in [Severity.HIGH, Severity.CRITICAL]:
            return 0.9
        return 0.4

    def _compute_uncertainty(self, event: Event) -> float:
        """Неопределённость (обратная уверенности)."""
        # Если в payload есть confidence, используем его
        confidence = event.payload.get("confidence", 0.8)
        return 1.0 - confidence


# Глобальный экземпляр
engine = SalienceEngine()


def get_salience_engine() -> SalienceEngine:
    return engine