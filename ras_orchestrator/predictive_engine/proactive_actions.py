"""
Генератор проактивных действий на основе прогнозов и паттернов.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from common.models import Forecast, Pattern, SystemMode

logger = logging.getLogger(__name__)


class ProactiveActionGenerator:
    """Генерирует проактивные действия для системы на основе анализа."""

    def __init__(self):
        self.action_templates = {
            "increase_mode": {
                "component": "mode_manager",
                "action": "switch_mode",
                "description": "Повысить режим системы из-за ожидаемого всплеска событий",
            },
            "adjust_salience_weights": {
                "component": "salience_engine",
                "action": "adjust_weights",
                "description": "Скорректировать веса значимости для типа событий",
            },
            "prewarm_agents": {
                "component": "task_orchestrator",
                "action": "scale_agents",
                "description": "Запустить дополнительные агенты заранее",
            },
            "notify_operators": {
                "component": "human_escalation",
                "action": "send_alert",
                "description": "Уведомить операторов о возможном инциденте",
            },
            "increase_monitoring": {
                "component": "observability",
                "action": "increase_frequency",
                "description": "Увеличить частоту сбора метрик",
            },
        }

    def generate_actions(
        self,
        event_type: str,
        patterns: Dict[str, List[Pattern]],
        forecast: Optional[Forecast],
        historical_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Генерирует список проактивных действий на основе анализа.
        """
        actions = []

        # 1. Действия на основе прогноза
        if forecast:
            actions.extend(self._actions_from_forecast(event_type, forecast))

        # 2. Действия на основе паттернов
        if patterns:
            actions.extend(self._actions_from_patterns(event_type, patterns))

        # 3. Действия на основе исторических данных
        if historical_data:
            actions.extend(self._actions_from_history(event_type, historical_data))

        # Дедупликация
        unique_actions = []
        seen = set()
        for act in actions:
            key = (act.get("component"), act.get("action"), str(act.get("parameters")))
            if key not in seen:
                seen.add(key)
                unique_actions.append(act)

        return unique_actions

    def _actions_from_forecast(
        self, event_type: str, forecast: Forecast
    ) -> List[Dict[str, Any]]:
        """Генерирует действия на основе прогноза."""
        actions = []

        # Анализируем прогнозируемые значения
        pred_values = [p.predicted_value for p in forecast.predictions]
        if not pred_values:
            return actions

        max_pred = max(pred_values)
        avg_pred = sum(pred_values) / len(pred_values)

        # Если прогнозируется высокий уровень значимости
        if max_pred > 0.8:
            actions.append({
                "component": "mode_manager",
                "action": "switch_mode",
                "parameters": {"target_mode": SystemMode.ELEVATED.value},
                "description": f"Прогнозируется пик значимости для {event_type} (max={max_pred:.2f})",
                "confidence": forecast.confidence_level,
            })
            actions.append({
                "component": "task_orchestrator",
                "action": "scale_agents",
                "parameters": {"delta": 2, "agent_type": "retriever"},
                "description": "Увеличить количество агентов для обработки ожидаемого всплеска",
                "confidence": forecast.confidence_level,
            })

        if avg_pred > 0.6:
            actions.append({
                "component": "salience_engine",
                "action": "adjust_weights",
                "parameters": {"event_type": event_type, "weight_multiplier": 1.2},
                "description": f"Увеличить вес значимости для {event_type}",
                "confidence": forecast.confidence_level,
            })

        # Если доверительный интервал широкий, увеличить мониторинг
        avg_interval_width = sum(
            (p.upper_bound - p.lower_bound) for p in forecast.predictions
        ) / len(forecast.predictions)
        if avg_interval_width > 0.3:
            actions.append({
                "component": "observability",
                "action": "increase_frequency",
                "parameters": {"metric": event_type, "factor": 2},
                "description": "Увеличить частоту мониторинга из-за высокой неопределённости прогноза",
                "confidence": forecast.confidence_level,
            })

        return actions

    def _actions_from_patterns(
        self, event_type: str, patterns: Dict[str, List[Pattern]]
    ) -> List[Dict[str, Any]]:
        """Генерирует действия на основе обнаруженных паттернов."""
        actions = []

        # Сезонность
        for pattern in patterns.get("seasonality", []):
            if pattern.confidence > 0.7:
                actions.append({
                    "component": "mode_manager",
                    "action": "schedule_mode_change",
                    "parameters": {
                        "event_type": event_type,
                        "pattern": "seasonality",
                        "peak_hours": list(pattern.parameters.get("hourly_means", {}).keys()),
                    },
                    "description": f"Запланировать изменение режима на основе сезонности {event_type}",
                    "confidence": pattern.confidence,
                })

        # Тренд
        for pattern in patterns.get("trend", []):
            slope = pattern.parameters.get("slope", 0)
            if slope > 0.01:  # Положительный тренд
                actions.append({
                    "component": "salience_engine",
                    "action": "adjust_weights",
                    "parameters": {"event_type": event_type, "weight_multiplier": 1.1},
                    "description": f"Учесть возрастающий тренд для {event_type}",
                    "confidence": pattern.confidence,
                })

        # Аномалии
        anomalies = patterns.get("anomalies", [])
        if len(anomalies) > 3:
            actions.append({
                "component": "human_escalation",
                "action": "send_alert",
                "parameters": {
                    "event_type": event_type,
                    "anomaly_count": len(anomalies),
                    "severity": "medium",
                },
                "description": f"Обнаружено {len(anomalies)} аномалий для {event_type}",
                "confidence": max(a.confidence for a in anomalies) if anomalies else 0.5,
            })

        return actions

    def _actions_from_history(
        self, event_type: str, historical_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Генерирует действия на основе исторических данных."""
        actions = []

        # Анализируем агрегированные данные
        if len(historical_data) < 10:
            return actions

        # Вычисляем статистику
        counts = [d.get("count", 0) for d in historical_data]
        avg_count = sum(counts) / len(counts)
        max_count = max(counts)

        # Если наблюдались пики нагрузки
        if max_count > avg_count * 3:
            actions.append({
                "component": "task_orchestrator",
                "action": "prepare_scaling",
                "parameters": {"event_type": event_type, "threshold": int(avg_count * 2)},
                "description": f"Подготовить масштабирование для {event_type} на основе исторических пиков",
                "confidence": 0.7,
            })

        return actions

    def format_action_for_execution(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Форматирует действие для выполнения системой."""
        return {
            "id": f"proactive_{datetime.utcnow().timestamp()}",
            "component": action["component"],
            "action_type": action["action"],
            "parameters": action.get("parameters", {}),
            "description": action.get("description", ""),
            "confidence": action.get("confidence", 0.5),
            "generated_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }