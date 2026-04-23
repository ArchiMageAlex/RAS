"""
Обнаружение паттернов во временных рядах: сезонность, тренды, аномалии, корреляции.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from common.models import Pattern

logger = logging.getLogger(__name__)


class PatternDetector:
    """Детектор паттернов во временных рядах."""

    def __init__(self, min_samples: int = 100):
        self.min_samples = min_samples

    def detect_seasonality(
        self, timestamps: List[datetime], values: List[float], period_hours: int = 24
    ) -> Optional[Pattern]:
        """
        Обнаруживает суточную сезонность.
        Использует автокорреляцию с заданным периодом.
        """
        if len(values) < self.min_samples:
            return None

        # Простой алгоритм: вычисляем среднее по часам
        hour_to_values = {}
        for ts, val in zip(timestamps, values):
            hour = ts.hour
            hour_to_values.setdefault(hour, []).append(val)

        if len(hour_to_values) < 2:
            return None

        hourly_means = {h: np.mean(vals) for h, vals in hour_to_values.items()}
        overall_mean = np.mean(values)
        # Мера сезонности: дисперсия средних по часам относительно общего среднего
        seasonal_variance = np.var(list(hourly_means.values()))

        confidence = min(seasonal_variance / (overall_mean + 1e-6), 1.0)

        return Pattern(
            pattern_type="seasonality",
            parameters={
                "period_hours": period_hours,
                "hourly_means": hourly_means,
                "seasonal_variance": float(seasonal_variance),
            },
            confidence=float(confidence),
            start_time=min(timestamps),
            end_time=max(timestamps),
        )

    def detect_trend(
        self, timestamps: List[datetime], values: List[float]
    ) -> Optional[Pattern]:
        """Обнаруживает линейный тренд."""
        if len(values) < 10:
            return None

        # Преобразуем временные метки в числовые значения (секунды от начала)
        t0 = timestamps[0].timestamp()
        t_numeric = np.array([(ts.timestamp() - t0) / 3600 for ts in timestamps])  # в часах
        vals = np.array(values)

        # Линейная регрессия
        coeffs = np.polyfit(t_numeric, vals, 1)
        slope = coeffs[0]  # наклон (тренд)
        intercept = coeffs[1]

        # Уверенность на основе R^2
        predicted = slope * t_numeric + intercept
        ss_res = np.sum((vals - predicted) ** 2)
        ss_tot = np.sum((vals - np.mean(vals)) ** 2)
        r2 = 1 - (ss_res / (ss_tot + 1e-6))
        confidence = abs(r2)

        return Pattern(
            pattern_type="trend",
            parameters={
                "slope": float(slope),
                "intercept": float(intercept),
                "r2": float(r2),
            },
            confidence=float(confidence),
            start_time=min(timestamps),
            end_time=max(timestamps),
        )

    def detect_anomalies(
        self, timestamps: List[datetime], values: List[float], z_threshold: float = 3.0
    ) -> List[Pattern]:
        """Обнаруживает аномалии с помощью z-score."""
        if len(values) < 5:
            return []

        vals = np.array(values)
        mean = np.mean(vals)
        std = np.std(vals) + 1e-6
        z_scores = np.abs((vals - mean) / std)

        anomalies = []
        for ts, val, z in zip(timestamps, values, z_scores):
            if z > z_threshold:
                anomalies.append(
                    Pattern(
                        pattern_type="anomaly",
                        parameters={
                            "value": float(val),
                            "z_score": float(z),
                            "mean": float(mean),
                            "std": float(std),
                        },
                        confidence=min(z / 5.0, 1.0),
                        start_time=ts,
                        end_time=ts,
                    )
                )
        return anomalies

    def detect_correlations(
        self,
        series1: List[float],
        series2: List[float],
        timestamps: List[datetime],
        lag_hours: int = 0,
    ) -> Optional[Pattern]:
        """Обнаруживает корреляцию между двумя рядами с возможным лагом."""
        if len(series1) != len(series2) or len(series1) < 10:
            return None

        # Применяем лаг
        if lag_hours > 0:
            series1 = series1[:-lag_hours]
            series2 = series2[lag_hours:]
            ts = timestamps[lag_hours:]
        else:
            ts = timestamps

        corr = np.corrcoef(series1, series2)[0, 1]
        if np.isnan(corr):
            return None

        confidence = abs(corr)
        return Pattern(
            pattern_type="correlation",
            parameters={
                "correlation": float(corr),
                "lag_hours": lag_hours,
                "series1_mean": float(np.mean(series1)),
                "series2_mean": float(np.mean(series2)),
            },
            confidence=float(confidence),
            start_time=min(ts),
            end_time=max(ts),
        )

    def detect_all(
        self, timestamps: List[datetime], values: List[float]
    ) -> Dict[str, List[Pattern]]:
        """Запускает все детекторы и возвращает словарь паттернов."""
        result = {
            "seasonality": [],
            "trend": [],
            "anomalies": [],
            "correlations": [],
        }

        seasonality = self.detect_seasonality(timestamps, values)
        if seasonality:
            result["seasonality"].append(seasonality)

        trend = self.detect_trend(timestamps, values)
        if trend:
            result["trend"].append(trend)

        anomalies = self.detect_anomalies(timestamps, values)
        result["anomalies"] = anomalies

        # Для корреляции нужен второй ряд - здесь не реализовано
        return result