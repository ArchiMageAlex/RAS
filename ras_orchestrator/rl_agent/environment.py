"""
Среда Reinforcement Learning для взаимодействия с оркестратором.
Определяет пространство состояний, действий и функцию вознаграждения.
"""

import logging
from typing import Dict, Any, Tuple, List, Optional
import numpy as np
from datetime import datetime, timedelta
from common.models import RLState, RLAction, SystemMetrics, SystemMode

logger = logging.getLogger(__name__)


class OrchestratorEnv:
    """
    Среда RL, имитирующая взаимодействие с оркестратором.
    Состояние: метрики системы, текущий режим, решения о прерываниях.
    Действия: корректировка порогов значимости, режимов, прерываний.
    """

    def __init__(self):
        # Пространство состояний (размерность)
        self.state_dim = 10  # примерное количество признаков
        # Пространство действий (дискретное)
        self.action_space = [
            "increase_salience_weight",
            "decrease_salience_weight",
            "increase_mode_threshold",
            "decrease_mode_threshold",
            "increase_interrupt_threshold",
            "decrease_interrupt_threshold",
            "no_op",
        ]
        self.action_dim = len(self.action_space)

        # Текущее состояние
        self.current_state: Optional[RLState] = None
        self.step_count = 0
        self.max_steps = 1000

        # Базовые пороги (будут корректироваться агентом)
        self.salience_weight = 1.0
        self.mode_thresholds = {
            SystemMode.LOW: 0.2,
            SystemMode.NORMAL: 0.5,
            SystemMode.ELEVATED: 0.7,
            SystemMode.CRITICAL: 0.9,
        }
        self.interrupt_threshold = 0.6

    def _mode_to_numeric(self, mode: SystemMode) -> float:
        mapping = {
            SystemMode.LOW: 0.0,
            SystemMode.NORMAL: 1.0,
            SystemMode.ELEVATED: 2.0,
            SystemMode.CRITICAL: 3.0,
        }
        return mapping.get(mode, 1.0)  # по умолчанию NORMAL

    def reset(self) -> RLState:
        """Сбрасывает среду в начальное состояние."""
        self.step_count = 0
        self.current_state = self._generate_initial_state()
        logger.info("Environment reset.")
        return self.current_state

    def _generate_initial_state(self) -> RLState:
        """Генерирует начальное состояние."""
        # Имитация метрик системы
        metrics = SystemMetrics(
            cpu_load=0.5,
            latency_ms=150.0,
            error_rate=0.01,
            queue_depth=20,
            memory_usage=0.6,
            throughput=50.0,
        )
        return RLState(
            timestamp=datetime.utcnow(),
            salience_scores=[0.5, 0.6, 0.4, 0.7],
            current_mode=SystemMode.NORMAL,
            interrupt_decisions=[
                {"event_id": "evt1", "decision": "allow", "confidence": 0.8},
                {"event_id": "evt2", "decision": "block", "confidence": 0.9},
            ],
            system_metrics=metrics,
        )

    def step(self, action: RLAction) -> Tuple[RLState, float, bool, Dict[str, Any]]:
        """
        Выполняет действие в среде и возвращает новое состояние, reward, done и info.
        """
        self.step_count += 1
        old_state = self.current_state

        # Применяем действие
        self._apply_action(action)

        # Генерируем новое состояние
        new_state = self._generate_next_state(old_state)
        self.current_state = new_state

        # Вычисляем reward
        reward = self._calculate_reward(old_state, new_state, action)

        # Проверяем завершение эпизода
        done = self.step_count >= self.max_steps

        info = {
            "step": self.step_count,
            "action": action.action_type,
            "salience_weight": self.salience_weight,
            "mode_thresholds": self.mode_thresholds,
        }

        return new_state, reward, done, info

    def _apply_action(self, action: RLAction):
        """Применяет действие, корректируя параметры системы."""
        if action.action_type == "adjust_salience_weights":
            delta = action.parameters.get("delta", 0.05)
            self.salience_weight += delta
            self.salience_weight = max(0.1, min(2.0, self.salience_weight))
            logger.debug(f"Adjusted salience weight to {self.salience_weight}")

        elif action.action_type == "adjust_mode_thresholds":
            mode = action.parameters.get("mode", "NORMAL")
            delta = action.parameters.get("delta", 0.02)
            try:
                mode_enum = SystemMode(mode)
                self.mode_thresholds[mode_enum] += delta
                self.mode_thresholds[mode_enum] = max(0.1, min(1.0, self.mode_thresholds[mode_enum]))
                logger.debug(f"Adjusted threshold for {mode} to {self.mode_thresholds[mode_enum]}")
            except ValueError:
                logger.warning(f"Unknown mode {mode}")

        elif action.action_type == "adjust_interrupt_thresholds":
            delta = action.parameters.get("delta", 0.03)
            self.interrupt_threshold += delta
            self.interrupt_threshold = max(0.1, min(1.0, self.interrupt_threshold))
            logger.debug(f"Adjusted interrupt threshold to {self.interrupt_threshold}")

    def _generate_next_state(self, old_state: RLState) -> RLState:
        """Генерирует следующее состояние на основе текущих параметров."""
        # Имитация изменений в системе
        import random
        metrics = old_state.system_metrics
        new_metrics = SystemMetrics(
            cpu_load=max(0.0, min(1.0, metrics.cpu_load + random.uniform(-0.05, 0.05))),
            latency_ms=max(0.0, metrics.latency_ms + random.uniform(-10, 10)),
            error_rate=max(0.0, min(1.0, metrics.error_rate + random.uniform(-0.005, 0.005))),
            queue_depth=max(0, metrics.queue_depth + random.randint(-5, 5)),
            memory_usage=max(0.0, min(1.0, metrics.memory_usage + random.uniform(-0.03, 0.03))),
            throughput=max(0.0, metrics.throughput + random.uniform(-5, 5)),
        )

        # Корректируем значимость на основе веса
        salience_scores = [
            min(1.0, score * self.salience_weight + random.uniform(-0.1, 0.1))
            for score in old_state.salience_scores
        ]

        # Определяем режим на основе порогов
        avg_salience = np.mean(salience_scores) if salience_scores else 0.5
        current_mode = SystemMode.NORMAL
        if avg_salience >= self.mode_thresholds[SystemMode.CRITICAL]:
            current_mode = SystemMode.CRITICAL
        elif avg_salience >= self.mode_thresholds[SystemMode.ELEVATED]:
            current_mode = SystemMode.ELEVATED
        elif avg_salience <= self.mode_thresholds[SystemMode.LOW]:
            current_mode = SystemMode.LOW

        return RLState(
            timestamp=datetime.utcnow(),
            salience_scores=salience_scores,
            current_mode=current_mode,
            interrupt_decisions=old_state.interrupt_decisions,  # упрощение
            system_metrics=new_metrics,
        )

    def _calculate_reward(
        self, old_state: RLState, new_state: RLState, action: RLAction
    ) -> float:
        """
        Вычисляет reward на основе изменений в системе.
        Цели:
          - Минимизировать ошибки
          - Поддерживать задержку низкой
          - Избегать частых переключений режимов
          - Максимизировать пропускную способность
        """
        reward = 0.0

        # Награда за снижение error_rate
        error_diff = old_state.system_metrics.error_rate - new_state.system_metrics.error_rate
        reward += error_diff * 10.0

        # Штраф за увеличение latency
        latency_diff = new_state.system_metrics.latency_ms - old_state.system_metrics.latency_ms
        reward -= latency_diff * 0.01

        # Награда за высокую пропускную способность
        throughput_diff = new_state.system_metrics.throughput - old_state.system_metrics.throughput
        reward += throughput_diff * 0.1

        # Штраф за частые изменения режимов
        if old_state.current_mode != new_state.current_mode:
            reward -= 0.5

        # Штраф за экстремальные корректировки
        if action.action_type != "no_op":
            reward -= 0.1  # небольшой штраф за любое действие

        # Награда за стабильность (малое изменение CPU)
        cpu_diff = abs(new_state.system_metrics.cpu_load - old_state.system_metrics.cpu_load)
        reward -= cpu_diff * 2.0

        return reward

    def get_state_vector(self, state: RLState) -> np.ndarray:
        """Преобразует состояние в вектор для нейронной сети."""
        # Простой пример: конкатенация ключевых метрик
        vec = [
            state.system_metrics.cpu_load,
            state.system_metrics.latency_ms / 1000.0,  # нормализация
            state.system_metrics.error_rate,
            state.system_metrics.queue_depth / 100.0,
            state.system_metrics.memory_usage,
            state.system_metrics.throughput / 100.0,
            np.mean(state.salience_scores) if state.salience_scores else 0.5,
            self._mode_to_numeric(state.current_mode),  # числовое представление
            self.salience_weight,
            self.interrupt_threshold,
        ]
        return np.array(vec, dtype=np.float32)

    def get_action_index(self, action: RLAction) -> int:
        """Возвращает индекс действия в пространстве действий."""
        # Простое сопоставление
        mapping = {
            "adjust_salience_weights": 0,
            "adjust_mode_thresholds": 1,
            "adjust_interrupt_thresholds": 2,
        }
        return mapping.get(action.action_type, 0)