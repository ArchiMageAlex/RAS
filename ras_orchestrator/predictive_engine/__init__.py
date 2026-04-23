"""
Predictive Engine для фазы 3 (Self-Optimizing).
Прогнозирование временных паттернов и проактивные действия.
"""

from .engine import PredictiveEngine

__version__ = "0.1.0"

# Глобальный экземпляр для удобства интеграции
_predictive_engine: PredictiveEngine = None

def get_predictive_engine() -> PredictiveEngine:
    """Возвращает глобальный экземпляр Predictive Engine."""
    global _predictive_engine
    if _predictive_engine is None:
        _predictive_engine = PredictiveEngine()
    return _predictive_engine

def set_predictive_engine(engine: PredictiveEngine):
    """Устанавливает пользовательский экземпляр Predictive Engine."""
    global _predictive_engine
    _predictive_engine = engine