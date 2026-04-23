"""
Основной движок прогнозирования, координирующий работу pattern detection, forecasting и proactive actions.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from common.models import Forecast, Pattern, EventType
from .timeseries_store import TimeseriesStore
from .pattern_detector import PatternDetector
from .forecast_models import get_forecast_model
from .proactive_actions import ProactiveActionGenerator

logger = logging.getLogger(__name__)


class PredictiveEngine:
    """Движок прогнозирования временных паттернов."""

    def __init__(
        self,
        timeseries_store: Optional[TimeseriesStore] = None,
        pattern_detector: Optional[PatternDetector] = None,
        forecast_model: str = "statistical",
    ):
        self.timeseries_store = timeseries_store or TimeseriesStore()
        self.pattern_detector = pattern_detector or PatternDetector()
        self.forecast_model_name = forecast_model
        self.forecast_model = None
        self.action_generator = ProactiveActionGenerator()
        self.last_analysis_time: Optional[datetime] = None

    async def initialize(self):
        """Инициализация движка (подключение к БД и т.д.)."""
        await self.timeseries_store.connect()
        logger.info("PredictiveEngine initialized.")

    async def shutdown(self):
        """Корректное завершение работы."""
        await self.timeseries_store.close()
        logger.info("PredictiveEngine shut down.")

    async def analyze_event_type(
        self, event_type: str, lookback_hours: int = 168
    ) -> Dict[str, Any]:
        """
        Анализирует исторические данные для указанного типа событий.
        Возвращает обнаруженные паттерны и прогноз.
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=lookback_hours)

        # Загружаем агрегированные данные
        aggregated = await self.timeseries_store.query_aggregated(
            start_time=start_time,
            end_time=end_time,
            aggregation_interval="1 hour",
            event_type=event_type,
        )

        if not aggregated:
            logger.warning(f"No data for event type {event_type} in the last {lookback_hours}h.")
            return {"event_type": event_type, "patterns": [], "forecast": None}

        # Извлекаем временные метки и значения
        timestamps = [row["timestamp"] for row in aggregated]
        values = [row["avg_salience"] for row in aggregated]

        # Обнаружение паттернов
        patterns = self.pattern_detector.detect_all(timestamps, values)

        # Прогнозирование
        forecast = await self.generate_forecast(event_type, timestamps, values)

        # Генерация проактивных действий
        actions = self.action_generator.generate_actions(
            event_type, patterns, forecast, aggregated
        )

        self.last_analysis_time = datetime.utcnow()

        return {
            "event_type": event_type,
            "patterns": patterns,
            "forecast": forecast,
            "proactive_actions": actions,
            "data_points": len(aggregated),
        }

    async def generate_forecast(
        self, event_type: str, timestamps: List[datetime], values: List[float]
    ) -> Optional[Forecast]:
        """Генерирует прогноз на основе исторических данных."""
        if len(values) < 24:
            logger.warning(f"Insufficient data for forecasting {event_type}.")
            return None

        if self.forecast_model is None:
            self.forecast_model = get_forecast_model(self.forecast_model_name)

        try:
            self.forecast_model.fit(timestamps, values)
            forecast = self.forecast_model.predict(datetime.utcnow())
            forecast.event_type = event_type
            return forecast
        except Exception as e:
            logger.error(f"Forecast generation failed: {e}")
            return None

    async def detect_anomalies_realtime(
        self, event_type: str, value: float, timestamp: datetime
    ) -> List[Pattern]:
        """Обнаруживает аномалии в реальном времени для входящего события."""
        # Загружаем последние данные для контекста
        end_time = timestamp
        start_time = end_time - timedelta(hours=24)
        aggregated = await self.timeseries_store.query_aggregated(
            start_time=start_time,
            end_time=end_time,
            event_type=event_type,
        )
        if not aggregated:
            return []

        values = [row["avg_salience"] for row in aggregated]
        timestamps = [row["timestamp"] for row in aggregated]

        # Добавляем текущее значение
        timestamps.append(timestamp)
        values.append(value)

        anomalies = self.pattern_detector.detect_anomalies(timestamps, values)
        return anomalies

    async def store_event_for_analysis(self, event: Dict[str, Any]) -> None:
        """Сохраняет событие в хранилище временных рядов для будущего анализа."""
        try:
            await self.timeseries_store.store_event_point(
                timestamp=event.get("timestamp", datetime.utcnow()),
                event_type=event.get("event_type", "unknown"),
                source=event.get("source", "unknown"),
                salience_aggregated=event.get("salience_aggregated", 0.5),
                severity=event.get("severity", "medium"),
                metadata=event.get("metadata", {}),
            )
        except Exception as e:
            logger.error(f"Failed to store event for analysis: {e}")

    async def get_recommended_actions(
        self, event_type: str, horizon_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Возвращает рекомендованные проактивные действия для типа событий."""
        analysis = await self.analyze_event_type(event_type, lookback_hours=168)
        return analysis.get("proactive_actions", [])

    async def get_system_health_forecast(self) -> Dict[str, Any]:
        """Прогнозирует общее здоровье системы на основе всех типов событий."""
        # Собираем все типы событий
        event_types = [et.value for et in EventType]
        forecasts = []
        for et in event_types:
            analysis = await self.analyze_event_type(et, lookback_hours=24)
            if analysis.get("forecast"):
                forecasts.append({
                    "event_type": et,
                    "forecast": analysis["forecast"],
                })

        # Агрегируем прогнозы
        overall_risk = 0.0
        if forecasts:
            # Усредняем максимальные предсказанные значения
            max_predictions = [
                max(p.predicted_value for p in f["forecast"].predictions)
                for f in forecasts if f["forecast"].predictions
            ]
            overall_risk = np.mean(max_predictions) if max_predictions else 0.0

        return {
            "timestamp": datetime.utcnow(),
            "forecasts": forecasts,
            "overall_risk": overall_risk,
            "recommendation": "normal" if overall_risk < 0.5 else "elevated",
        }


# Глобальный экземпляр для использования
predictive_engine = PredictiveEngine()