"""
Модели прогнозирования временных рядов: Prophet, LSTM, статистические.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from common.models import Forecast, ForecastPoint

logger = logging.getLogger(__name__)


class BaseForecastModel:
    """Базовый класс для моделей прогнозирования."""

    def __init__(self, horizon_hours: int = 24):
        self.horizon_hours = horizon_hours

    def fit(self, timestamps: List[datetime], values: List[float]) -> None:
        """Обучает модель на исторических данных."""
        raise NotImplementedError

    def predict(self, start_time: datetime) -> Forecast:
        """Генерирует прогноз на заданный горизонт."""
        raise NotImplementedError


class StatisticalModel(BaseForecastModel):
    """Простая статистическая модель (скользящее среднее + сезонность)."""

    def __init__(self, horizon_hours: int = 24, window_size: int = 24):
        super().__init__(horizon_hours)
        self.window_size = window_size
        self.timestamps: List[datetime] = []
        self.values: List[float] = []
        self.seasonal_factors: Dict[int, float] = {}

    def fit(self, timestamps: List[datetime], values: List[float]) -> None:
        self.timestamps = timestamps
        self.values = values
        # Вычисляем сезонные факторы по часам
        hour_to_vals = {}
        for ts, val in zip(timestamps, values):
            hour = ts.hour
            hour_to_vals.setdefault(hour, []).append(val)
        self.seasonal_factors = {
            h: np.mean(vals) / (np.mean(values) + 1e-6)
            for h, vals in hour_to_vals.items()
        }

    def predict(self, start_time: datetime) -> Forecast:
        if len(self.values) < self.window_size:
            # Недостаточно данных - возвращаем среднее
            base = np.mean(self.values) if self.values else 0.5
        else:
            # Скользящее среднее
            recent = self.values[-self.window_size:]
            base = np.mean(recent)

        predictions = []
        for i in range(self.horizon_hours):
            ts = start_time + timedelta(hours=i)
            hour = ts.hour
            seasonal = self.seasonal_factors.get(hour, 1.0)
            pred = base * seasonal
            # Добавляем шум для имитации доверительного интервала
            lower = pred * 0.8
            upper = pred * 1.2
            predictions.append(
                ForecastPoint(
                    timestamp=ts,
                    predicted_value=float(pred),
                    lower_bound=float(lower),
                    upper_bound=float(upper),
                )
            )

        return Forecast(
            event_type="generic",
            horizon_hours=self.horizon_hours,
            confidence_level=0.7,
            predictions=predictions,
            recommended_actions=[],
        )


class ProphetModel(BaseForecastModel):
    """Обёртка над Facebook Prophet (если установлен)."""

    def __init__(self, horizon_hours: int = 24):
        super().__init__(horizon_hours)
        self.model = None
        self.fitted = False

    def fit(self, timestamps: List[datetime], values: List[float]) -> None:
        try:
            from prophet import Prophet
        except ImportError:
            logger.warning("Prophet not installed, using statistical model as fallback.")
            self.model = None
            self.fitted = False
            return

        # Подготовка данных для Prophet
        import pandas as pd
        df = pd.DataFrame({
            'ds': timestamps,
            'y': values,
        })
        self.model = Prophet()
        self.model.fit(df)
        self.fitted = True

    def predict(self, start_time: datetime) -> Forecast:
        if not self.fitted or self.model is None:
            # Fallback
            stat_model = StatisticalModel(self.horizon_hours)
            stat_model.fit([], [])
            return stat_model.predict(start_time)

        import pandas as pd
        future = self.model.make_future_dataframe(periods=self.horizon_hours, freq='H')
        forecast_df = self.model.predict(future)

        # Отфильтруем только будущие периоды
        future_df = forecast_df[forecast_df['ds'] >= start_time].head(self.horizon_hours)

        predictions = []
        for _, row in future_df.iterrows():
            predictions.append(
                ForecastPoint(
                    timestamp=row['ds'],
                    predicted_value=float(row['yhat']),
                    lower_bound=float(row['yhat_lower']),
                    upper_bound=float(row['yhat_upper']),
                )
            )

        return Forecast(
            event_type="generic",
            horizon_hours=self.horizon_hours,
            confidence_level=0.8,
            predictions=predictions,
            recommended_actions=[],
        )


class LSTMModel(BaseForecastModel):
    """LSTM модель на основе PyTorch (заглушка)."""

    def __init__(self, horizon_hours: int = 24, seq_length: int = 24):
        super().__init__(horizon_hours)
        self.seq_length = seq_length
        self.model = None
        self.scaler = None
        self.fitted = False

    def fit(self, timestamps: List[datetime], values: List[float]) -> None:
        logger.info("LSTM fitting is not implemented (requires PyTorch).")
        self.fitted = False

    def predict(self, start_time: datetime) -> Forecast:
        # Заглушка
        stat_model = StatisticalModel(self.horizon_hours)
        stat_model.fit([], [])
        return stat_model.predict(start_time)


def get_forecast_model(model_name: str = "statistical", **kwargs) -> BaseForecastModel:
    """Фабрика моделей прогнозирования."""
    if model_name == "prophet":
        return ProphetModel(**kwargs)
    elif model_name == "lstm":
        return LSTMModel(**kwargs)
    else:
        return StatisticalModel(**kwargs)