"""
Расширенные алгоритмы оценки значимости и ML-модели для anomaly detection.
"""
import hashlib
import json
import logging
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
from common.models import Event, Severity

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Простой детектор аномалий на основе статистики исторических событий."""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.event_history = []  # список значений salience aggregated
        self.stats = {"mean": 0.5, "std": 0.2}

    def update(self, score: float):
        """Обновляет историю и статистику."""
        self.event_history.append(score)
        if len(self.event_history) > self.window_size:
            self.event_history.pop(0)
        if len(self.event_history) >= 10:
            arr = np.array(self.event_history)
            self.stats["mean"] = float(np.mean(arr))
            self.stats["std"] = float(np.std(arr)) + 1e-6

    def detect(self, score: float, threshold: float = 2.0) -> Tuple[bool, float]:
        """
        Определяет, является ли оценка аномальной (z-score).
        Возвращает (is_anomaly, z_score).
        """
        if self.stats["std"] == 0:
            return False, 0.0
        z = (score - self.stats["mean"]) / self.stats["std"]
        return abs(z) > threshold, z


class SimilarityCache:
    """LRU-кэш для результатов оценки похожих событий."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.cache = OrderedDict()  # key -> (score, timestamp)

    def _make_key(self, event: Event) -> str:
        """Создаёт ключ на основе типа, severity и payload."""
        # Упрощённый ключ: можно улучшить для более точного определения похожести
        data = {
            "type": event.type,
            "severity": event.severity,
            "payload_hash": hashlib.md5(
                json.dumps(event.payload, sort_keys=True).encode()
            ).hexdigest()[:8],
        }
        return json.dumps(data, sort_keys=True)

    def get(self, event: Event) -> Optional[float]:
        """Получает кэшированную агрегированную оценку."""
        key = self._make_key(event)
        if key not in self.cache:
            return None
        score, timestamp = self.cache[key]
        if time.time() - timestamp > self.ttl:
            del self.cache[key]
            return None
        # Перемещаем в конец (последний использованный)
        self.cache.move_to_end(key)
        return score

    def set(self, event: Event, score: float):
        """Сохраняет оценку в кэш."""
        key = self._make_key(event)
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)  # удаляем самый старый
        self.cache[key] = (score, time.time())


class ExternalContextClient:
    """Клиент для получения внешнего контекста (заглушка)."""

    def __init__(self, endpoint: str = "http://localhost:8080"):
        self.endpoint = endpoint

    def fetch_context(self, event: Event) -> Dict[str, Any]:
        """
        Запрашивает дополнительный контекст для события.
        В реальности может обращаться к базам данных, API и т.д.
        """
        # Заглушка: возвращаем фиктивные данные
        return {
            "related_incidents": 0,
            "system_load": 0.5,
            "time_of_day": datetime.utcnow().hour,
            "day_of_week": datetime.utcnow().weekday(),
        }


class AdvancedScoring:
    """
    Улучшенные алгоритмы оценки значимости с поддержкой:
    - Конфигурируемых весов по типам событий
    - Внешнего контекста
    - Аномалий
    """

    def __init__(
        self,
        default_weights: Optional[Dict[str, float]] = None,
        event_type_weights: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        # Веса по умолчанию (как в engine.py)
        self.default_weights = default_weights or {
            "relevance": 0.3,
            "novelty": 0.2,
            "risk": 0.25,
            "urgency": 0.15,
            "uncertainty": 0.1,
        }
        # Веса для конкретных типов событий (переопределяют default)
        self.event_type_weights = event_type_weights or {
            "security_alert": {"risk": 0.4, "urgency": 0.3, "relevance": 0.2},
            "payment_outage": {"urgency": 0.4, "risk": 0.3, "relevance": 0.2},
            "performance_degradation": {"relevance": 0.4, "risk": 0.3},
        }
        self.cache = SimilarityCache()
        self.anomaly_detector = AnomalyDetector()
        self.external_client = ExternalContextClient()

    def compute_relevance(self, event: Event, context: Dict[str, Any]) -> float:
        """Релевантность с учётом внешнего контекста."""
        base = self._base_relevance(event)
        # Увеличиваем релевантность, если есть связанные инциденты
        related_incidents = context.get("related_incidents", 0)
        if related_incidents > 0:
            base = min(1.0, base + 0.2)
        return base

    def _base_relevance(self, event: Event) -> float:
        """Базовая релевантность (как в engine.py)."""
        severity_map = {
            Severity.LOW: 0.2,
            Severity.MEDIUM: 0.5,
            Severity.HIGH: 0.8,
            Severity.CRITICAL: 1.0,
        }
        return severity_map.get(event.severity, 0.5)

    def compute_novelty(self, event: Event, context: Dict[str, Any]) -> float:
        """
        Новизна на основе исторической частоты и времени суток.
        """
        # Заглушка: можно интегрировать с хранилищем событий
        hour = context.get("time_of_day", 12)
        # Ночью события считаем более новыми (меньше фонового шума)
        if 0 <= hour < 6:
            return 0.7
        return 0.3

    def compute_risk(self, event: Event, context: Dict[str, Any]) -> float:
        """Риск с учётом системной нагрузки и типа события."""
        system_load = context.get("system_load", 0.5)
        base_risk = 0.4
        if event.type == "security_alert":
            base_risk = 0.9
        elif event.type == "payment_outage":
            base_risk = 0.8
        # Риск увеличивается при высокой нагрузке
        risk = min(1.0, base_risk + system_load * 0.2)
        return risk

    def compute_urgency(self, event: Event, context: Dict[str, Any]) -> float:
        """Срочность зависит от severity и дня недели."""
        if event.severity in [Severity.HIGH, Severity.CRITICAL]:
            base = 0.9
        else:
            base = 0.4
        # В выходные срочность может быть ниже (заглушка)
        day_of_week = context.get("day_of_week", 0)  # 0 = понедельник
        if day_of_week >= 5:  # суббота, воскресенье
            base *= 0.8
        return base

    def compute_uncertainty(self, event: Event, context: Dict[str, Any]) -> float:
        """Неопределённость на основе confidence и внешнего контекста."""
        confidence = event.payload.get("confidence", 0.8)
        # Если системная нагрузка высокая, неопределённость увеличивается
        system_load = context.get("system_load", 0.5)
        uncertainty = 1.0 - confidence
        uncertainty = min(1.0, uncertainty + system_load * 0.1)
        return uncertainty

    def get_weights_for_event(self, event_type: str) -> Dict[str, float]:
        """Возвращает веса для данного типа события."""
        weights = self.default_weights.copy()
        if event_type in self.event_type_weights:
            weights.update(self.event_type_weights[event_type])
        return weights

    def compute(self, event: Event) -> Dict[str, Any]:
        """
        Вычисляет расширенную оценку значимости с использованием кэша,
        внешнего контекста и детекции аномалий.
        Возвращает словарь с полными результатами.
        """
        # Проверка кэша
        cached = self.cache.get(event)
        if cached is not None:
            logger.debug(f"Cache hit for event {event.event_id}")
            return {"aggregated": cached, "cached": True}

        # Получение внешнего контекста
        context = self.external_client.fetch_context(event)

        # Вычисление компонентов
        relevance = self.compute_relevance(event, context)
        novelty = self.compute_novelty(event, context)
        risk = self.compute_risk(event, context)
        urgency = self.compute_urgency(event, context)
        uncertainty = self.compute_uncertainty(event, context)

        # Взвешенное агрегирование
        weights = self.get_weights_for_event(event.type)
        aggregated = (
            relevance * weights["relevance"]
            + novelty * weights["novelty"]
            + risk * weights["risk"]
            + urgency * weights["urgency"]
            + uncertainty * weights["uncertainty"]
        )
        aggregated = max(0.0, min(1.0, aggregated))

        # Детекция аномалий
        is_anomaly, z_score = self.anomaly_detector.detect(aggregated)
        self.anomaly_detector.update(aggregated)

        # Кэширование
        self.cache.set(event, aggregated)

        result = {
            "relevance": relevance,
            "novelty": novelty,
            "risk": risk,
            "urgency": urgency,
            "uncertainty": uncertainty,
            "aggregated": aggregated,
            "weights": weights,
            "is_anomaly": is_anomaly,
            "z_score": z_score,
            "context": context,
            "cached": False,
        }
        return result